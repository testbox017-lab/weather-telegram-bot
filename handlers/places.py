"""Роутер places: «Мои места» — /add, /places, /del, кнопки списка, ⭐ под прогнозом и /compare."""
import asyncio
import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
from charts import compare_chart
from core import (ASK_PLACE, BTN_PLACES, INPUT_TEXT, KEEP_INPUT, Input, drop_prompt, fmt_place, menu,
                  open_places_markup, place_name, saved, send_prompt, short_name, with_place)
from i18n import _
from places import DEFAULT_NAME, FAV_LIMIT, build_cb, coords_name, parse_coords
from weather import Place
from weekend import compare_text

router = Router(name="places")


def places_view(user_id: int, deleting: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    items = saved.list(user_id)
    if deleting:
        rows = [[InlineKeyboardButton(text=f"❌ {p.name}"[:60], callback_data=f"pl:ask:{i}")]
                for i, p in enumerate(items)]
        rows.append([InlineKeyboardButton(text=_("↩️ Готово"), callback_data="pl:list")])
        return _("Нажмите место, которое нужно удалить:"), InlineKeyboardMarkup(inline_keyboard=rows)
    rows = [[InlineKeyboardButton(text=f"📍 {p.name}"[:60], callback_data=build_cb(1, p.lat, p.lon))]
            for p in items]
    actions = [InlineKeyboardButton(text=_("➕ Добавить"), callback_data="pl:add")]
    if items:
        actions.append(InlineKeyboardButton(text=_("🗑 Удалить"), callback_data="pl:del"))
    if len(items) >= 2:
        actions.append(InlineKeyboardButton(text=_("📊 Сравнить"), callback_data="pl:cmp"))
    rows.append(actions)
    if items:
        text = _("⭐ Мои места:") + "\n" + "\n".join(f"{i}. {fmt_place(p)}" for i, p in enumerate(items, 1))
    else:
        text = _("⭐ Список мест пуст. Нажмите «➕ Добавить» или используйте /add <i>город</i>")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)



# ---------- Мои места ----------

async def save_place(m: Message, user_id: int, place: Place):
    result = saved.add(user_id, place)
    text = {
        "added": _("✅ Добавлено: {place}", place=fmt_place(place)),
        "updated": _("✅ Обновлено: {place}", place=fmt_place(place)),
        "exists": _("Уже есть в ваших местах: {place}", place=fmt_place(place)),
        "full": _("В списке уже {n} мест — удалите лишнее через /places", n=FAV_LIMIT),
    }[result]
    await m.answer(text, reply_markup=open_places_markup())


async def ask_place(m: Message, state: FSMContext):
    await state.set_state(Input.place)
    await send_prompt(m, state, _(ASK_PLACE))


@router.message(Input.place, INPUT_TEXT, flags=KEEP_INPUT)
async def place_input(m: Message, state: FSMContext):
    """Ответ на «Отправьте название города…»: город или координаты."""
    uid = m.from_user.id
    if await with_place(m, uid, m.text, lambda target, place: save_place(target, uid, place)):
        await drop_prompt(m.bot, m.chat.id, state)
        await state.clear()
    # не нашлось — ожидание остаётся, можно попробовать ещё раз


@router.message(Input.place, F.location, flags=KEEP_INPUT)
async def place_location(m: Message, state: FSMContext):
    await drop_prompt(m.bot, m.chat.id, state)
    await state.clear()
    loc = m.location
    await save_place(m, m.from_user.id, Place(coords_name(loc.latitude, loc.longitude), loc.latitude, loc.longitude))


@router.message(Command("add"))
async def add_cmd(m: Message, command: CommandObject, state: FSMContext):
    uid = m.from_user.id
    query = (command.args or "").strip()
    if not query:
        await ask_place(m, state)
        return
    if query.split(maxsplit=1)[0].replace(".", "").replace(",", "").lstrip("-+").isdigit() \
            and not parse_coords(query):
        await m.answer(_("Не понял координаты. Пример: <code>/add 51.18 32.83 Дача</code> "
                         "(широта от -90 до 90, долгота от -180 до 180)"))
        return
    await with_place(m, uid, query, lambda target, place: save_place(target, uid, place))


@router.message(Command("places"))
async def places_cmd(m: Message):
    text, markup = places_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.message(Command("del"))
async def del_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    key = (command.args or "").strip()
    if not saved.list(uid):
        await m.answer(_("Список мест пуст."), reply_markup=open_places_markup())
        return
    if not key:
        text, markup = places_view(uid, deleting=True)
        await m.answer(text, reply_markup=markup)
        return
    removed = saved.remove_by(uid, key)
    if removed:
        await m.answer(_("🗑 Удалено: {place}", place=fmt_place(removed)), reply_markup=open_places_markup())
    else:
        await m.answer(_("Не нашёл «{key}» в ваших местах. Номера — в /places", key=escape(key)))


@router.message(menu(BTN_PLACES))
async def btn_places(m: Message):
    await places_cmd(m)


@router.callback_query(F.data.startswith("pl:"))
async def on_places_button(cb: CallbackQuery, state: FSMContext):
    if not isinstance(cb.message, Message):
        await cb.answer(_("Сообщение устарело, откройте /places"), show_alert=True)
        return
    uid, action = cb.from_user.id, cb.data[3:]
    if action == "add":
        await cb.answer()
        await ask_place(cb.message, state)
        return
    if action == "cmp":
        await cb.answer()
        await send_compare(cb.message, uid)
        return
    if action.startswith("ask:"):  # первый шаг удаления — переспросить
        items = saved.list(uid)
        i = int(action[4:]) if action[4:].isdigit() else -1
        if not 0 <= i < len(items):
            await cb.answer(_("Уже удалено"))
        else:
            await cb.answer()
            confirm = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=_("🗑 Да, удалить"), callback_data=f"pl:rm:{i}"),
                InlineKeyboardButton(text=_("↩️ Нет"), callback_data="pl:del")]])
            try:
                await cb.message.edit_text(_("Удалить «{name}» из ваших мест?", name=escape(items[i].name)),
                                           reply_markup=confirm)
                return
            except Exception:
                pass
        action = "del"
    if action.startswith("rm:"):
        removed = saved.remove(uid, int(action[3:])) if action[3:].isdigit() else None
        await cb.answer(_("Удалено: {name}", name=removed.name) if removed else _("Уже удалено"))
        deleting = bool(saved.list(uid))
    else:
        await cb.answer()
        deleting = action == "del"
    text, markup = places_view(uid, deleting=deleting)
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:  # например, «message is not modified»
        await cb.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("fa:"))
async def on_save_button(cb: CallbackQuery):
    try:
        _kind, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer(_("Кнопка устарела"), show_alert=True)
        return
    name = place_name(cb.from_user.id, lat, lon)
    place = Place(coords_name(lat, lon) if name == _(DEFAULT_NAME) else name, lat, lon)
    result = saved.add(cb.from_user.id, place)
    await cb.answer({"added": _("⭐ Добавлено: {name}", name=place.name), "updated": _("⭐ Обновлено"),
                     "exists": _("Уже есть в ваших местах"),
                     "full": _("В списке уже {n} мест", n=FAV_LIMIT)}[result], show_alert=result == "full")



async def send_compare(m: Message, user_id: int):
    items = saved.list(user_id)
    if len(items) < 2:
        await m.answer(_("Для сравнения нужно хотя бы два места в «⭐ Мои места» — добавьте их через /add"),

                       reply_markup=open_places_markup())
        return

    async def one(p: Place):
        try:
            return await core.client.fetch(p, 7)
        except Exception:
            logging.exception("compare fetch error")
            return None

    results = await asyncio.gather(*(one(p) for p in items))
    text = compare_text([(escape(p.name), d) for p, d in zip(items, results)])
    series = [(short_name(p.name), d["daily"]["time"], d["daily"]["temperature_2m_max"], d["daily"]["temperature_2m_min"])
              for p, d in zip(items, results) if d and d.get("daily")]
    png = None
    if series:
        try:
            png = await asyncio.to_thread(compare_chart, series)
        except Exception:
            logging.exception("compare chart error")
    markup = open_places_markup()
    if png and len(text) <= 1024:
        await m.answer_photo(BufferedInputFile(png, filename="compare.png"), caption=text, reply_markup=markup)
        return
    await m.answer(text, reply_markup=markup)
    if png:
        await m.answer_photo(BufferedInputFile(png, filename="compare.png"))



@router.message(Command("compare"))
async def compare_cmd(m: Message):
    await send_compare(m, m.from_user.id)



