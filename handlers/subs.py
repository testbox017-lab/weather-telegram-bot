"""Роутер subs: рассылка погоды по расписанию — /subscribe, /subs, /unsubscribe, кнопки
и фоновая задача scheduler()."""
import asyncio
import logging
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
import health
from core import (BTN_SUBS, INPUT_TEXT, KEEP_INPUT, NO_PLACE, ChatTarget, Input, cancel_markup, keyboard,
                  last_places, place_data, place_from, place_name, send_weather, subs, with_place)
from places import build_cb, parse_coords
from subs import (MAX_TIMES, SUB_LIMIT, Subscriptions, condition_met, describe as describe_sched, describe_cond,
                  local_time, parse_schedule, run_due, split_condition, split_place_schedule, split_short)
from weather import Place, format_short

router = Router(name="subs")

def sched_cb(kind: str, value: str, place: Place) -> str:
    """kind: 'h' — каждые N часов, 't' — время ЧЧММ, 'i' — ввести своё время."""
    return f"s{kind}:{value}:{place.lat:.3f}:{place.lon:.3f}"


def schedule_markup(place: Place) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="Каждый час", callback_data=sched_cb("h", "1", place)),
         b(text="Каждые 3 ч", callback_data=sched_cb("h", "3", place))],
        [b(text="Каждые 6 ч", callback_data=sched_cb("h", "6", place)),
         b(text="Каждые 12 ч", callback_data=sched_cb("h", "12", place))],
        [b(text=f"{t}", callback_data=sched_cb("t", t.replace(":", ""), place))
         for t in ("07:00", "08:00", "09:00", "20:00")],
        [b(text="✏️ Своё время", callback_data=sched_cb("i", "0", place)),
         b(text="✖️ Отмена", callback_data="x")],
    ])


def fmt_label(sub: dict) -> str:
    return "кратко" if sub.get("short") else "полно"


def sub_text(sub: dict) -> str:
    """«по будням в 07:30, если будут осадки, кратко»."""
    parts = [describe_sched(sub["sched"]), describe_cond(sub.get("cond")), fmt_label(sub)]
    return ", ".join(p for p in parts if p)


def sub_created_markup(sub: dict) -> InlineKeyboardMarkup:
    other = "🖼 Присылать полностью" if sub.get("short") else "📄 Присылать кратко"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=other, callback_data=f"su:fmt1:{sub['id']}"),
        InlineKeyboardButton(text="🔔 Мои рассылки", callback_data="su:list")]])


def subs_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = subs.list(user_id)
    rows = [[InlineKeyboardButton(text=f"❌ {i}. {s['name']} — {describe_sched(s['sched'])}"[:50],
                                  callback_data=f"su:rm:{s['id']}"),
             InlineKeyboardButton(text="🖼 Полно" if s.get("short") else "📄 Кратко",
                                  callback_data=f"su:fmt:{s['id']}")] for i, s in enumerate(items, 1)]
    rows.append([InlineKeyboardButton(text="➕ Новая рассылка", callback_data="su:new")])
    if not items:
        return ("🔔 Рассылок пока нет. Бот может сам присылать погоду каждый час, раз в сутки или в "
                "выбранное время.", InlineKeyboardMarkup(inline_keyboard=rows))
    lines = [f"{i}. {escape(s['name'])} — {sub_text(s)}, следующая "
             f"{local_time(datetime.fromisoformat(s['next']), s['tz'])}"
             for i, s in enumerate(items, 1)]
    return "🔔 Ваши рассылки (❌ — отключить, 📄/🖼 — краткий или полный формат):\n" + "\n".join(lines), \
        InlineKeyboardMarkup(inline_keyboard=rows)


async def ask_schedule(m: Message, place: Place):
    await m.answer(f"🔔 Как часто присылать погоду для «{escape(place.name)}»?\n"
                   "Время для ежедневной рассылки — по местному времени этого места.",
                   reply_markup=schedule_markup(place))


async def create_sub(m: Message, user_id: int, place: Place, sched: dict, short: bool = False,
                     cond: str | None = None):
    try:
        tz = await core.client.timezone(place)
    except Exception:
        logging.exception("timezone error")
        await m.answer("Не удалось узнать часовой пояс места, попробуйте чуть позже 🙏")
        return
    sub = subs.add(user_id, place, sched, tz, datetime.now(timezone.utc), short=short, cond=cond)
    if not sub:
        await m.answer(f"У вас уже {SUB_LIMIT} рассылок — отключите лишнюю в /subs")
        return
    await m.answer(f"✅ Рассылка включена: {escape(place.name)} — {sub_text(sub)}.\n"
                   f"Следующая: {local_time(datetime.fromisoformat(sub['next']), tz)} ({tz}).\n"
                   "Управление — /subs", reply_markup=sub_created_markup(sub))


@router.message(Command("subscribe"))
async def subscribe_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    args, short = split_short(command.args)
    args, cond, has_if = split_condition(args)
    if has_if and not cond:
        await m.answer("Не понял условие. Примеры: <code>если дождь</code>, <code>если снег</code>, "
                       "<code>если мороз</code>, <code>если ниже -5</code>, <code>если выше 25</code>")
        return
    coords = parse_coords(args)
    query, sched = (args, None) if coords and not coords[2] else split_place_schedule(args)
    if cond and not sched:
        await m.answer("Для рассылки с условием укажите и время, например: "
                       "<code>/subscribe Бахмач 07:00 если дождь</code>")
        return

    async def subscribe(target: Message, place: Place):
        if sched:
            await create_sub(target, uid, place, sched, short, cond)
        else:
            await ask_schedule(target, place)

    if query:
        await with_place(m, uid, query, subscribe)
        return
    place = last_places.get(uid)
    if not place:
        await m.answer(NO_PLACE, reply_markup=keyboard)
        return
    await subscribe(m, place)


@router.message(Command("subs"))
async def subs_cmd(m: Message):
    text, markup = subs_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.message(F.text == BTN_SUBS)
async def btn_subs(m: Message):
    await subs_cmd(m)


@router.message(Command("unsubscribe"))
async def unsubscribe_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    key = (command.args or "").strip().lower()
    if not key:
        text, markup = subs_view(uid)
        await m.answer(text, reply_markup=markup)
        return
    if key in ("all", "все", "всё"):
        n = subs.remove_all(uid)
        await m.answer(f"🔕 Отключено рассылок: {n}" if n else "Рассылок не было.")
        return
    removed = subs.remove_index(uid, int(key)) if key.isdigit() else None
    if removed:
        await m.answer(f"🔕 Отключена: {escape(removed['name'])} — {describe_sched(removed['sched'])}")
    else:
        await m.answer("Нет рассылки с таким номером. Список — /subs")


@router.callback_query(F.data.startswith("sb:"))
async def on_subscribe_button(cb: CallbackQuery):
    try:
        _, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    await cb.answer()
    if isinstance(cb.message, Message):
        await ask_schedule(cb.message, Place(place_name(cb.from_user.id, lat, lon), lat, lon))


@router.callback_query(F.data.regexp(r"^s[hti]:"))
async def on_schedule_button(cb: CallbackQuery, state: FSMContext):
    try:
        kind, value, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, используйте /subscribe", show_alert=True)
        return
    await cb.answer()
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    if kind == "si":
        await state.set_state(Input.sub_time)
        await state.set_data(place_data(place))
        await cb.message.answer(f"Напишите время (до {MAX_TIMES}), например <code>07:30</code> или "
                                "<code>08:00, 20:00</code>", reply_markup=cancel_markup())
        return
    sched = parse_schedule(value if kind == "sh" else f"{value[:2]}:{value[2:]}")
    if not sched:
        await cb.message.answer("Не понял расписание, попробуйте /subscribe ещё раз")
        return
    await create_sub(cb.message, cb.from_user.id, place, sched)


@router.callback_query(F.data.startswith("su:"))
async def on_subs_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, откройте /subs", show_alert=True)
        return
    uid, action = cb.from_user.id, cb.data[3:]
    if action == "new":
        await cb.answer()
        place = last_places.get(uid)
        if not place:
            await cb.message.answer(NO_PLACE, reply_markup=keyboard)
        else:
            await ask_schedule(cb.message, place)
        return
    kind, _, sub_id = action.partition(":")
    if kind in ("fmt", "fmt1"):
        sub = subs.toggle_short(uid, int(sub_id)) if sub_id.isdigit() else None
        if not sub:
            await cb.answer("Рассылка уже отключена", show_alert=True)
            return
        await cb.answer("Теперь кратко: три строки без графиков" if sub.get("short") else "Теперь полностью, с графиками")
        if kind == "fmt1":  # кнопка под сообщением «Рассылка включена»
            try:
                await cb.message.edit_reply_markup(reply_markup=sub_created_markup(sub))
            except Exception:
                pass
            return
    elif kind == "rm":
        removed = subs.remove(uid, int(sub_id)) if sub_id.isdigit() else None
        await cb.answer("🔕 Рассылка отключена" if removed else "Уже отключена")
    else:
        await cb.answer()
    text, markup = subs_view(uid)
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:
        await cb.message.answer(text, reply_markup=markup)


@router.message(Input.sub_time, INPUT_TEXT, flags=KEEP_INPUT)
async def sub_time_input(m: Message, state: FSMContext):
    """Ответ на «Напишите время» после кнопки «✏️ Своё время»."""
    sched = parse_schedule(m.text)
    if not sched or "times" not in sched:  # состояние остаётся — можно попробовать ещё раз
        await m.answer(f"Не понял время. Пример: <code>07:30</code> или <code>08:00, 20:00</code> "
                       f"(не больше {MAX_TIMES})", reply_markup=cancel_markup())
        return
    place = place_from(await state.get_data())
    await state.clear()
    await create_sub(m, m.from_user.id, place, sched)


async def scheduler(bot: Bot, every: float = 30):
    """Фоновая задача: раз в `every` секунд отправляет наступившие рассылки."""
    logging.info("scheduler started: %d subscriptions", sum(len(v) for v in subs._data.values()))

    async def send(uid: int, sub: dict):
        place = Subscriptions.place(sub)
        data = await core.client.fetch(place, 1)
        if not condition_met(sub.get("cond"), data):
            logging.info("subscription %s/%s skipped: condition %s not met", uid, sub["id"], sub.get("cond"))
            return
        if sub.get("short"):
            more = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="📊 Подробно", callback_data=build_cb(1, place.lat, place.lon))]])
            await bot.send_message(uid, "🔔 " + format_short(escape(place.name), data), reply_markup=more)
            return
        await send_weather(ChatTarget(bot, uid), place, 1,
                           header=f"🔔 <b>Рассылка:</b> {sub_text(sub)}\n", data=data)

    while True:
        health.mark_tick()
        try:
            n = await run_due(subs, datetime.now(timezone.utc), send, (TelegramForbiddenError,))
            if n:
                logging.info("scheduler: sent %d", n)
        except Exception:
            logging.exception("scheduler error")
        await asyncio.sleep(every)



