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
from core import (ASK_PLACE, BTN_PLACES, INPUT_TEXT, KEEP_INPUT, Input, cancel_markup, fmt_place,
                  open_places_markup, place_name, saved, with_place)
from places import DEFAULT_NAME, FAV_LIMIT, build_cb, coords_name, parse_coords
from weather import Place
from weekend import compare_text

router = Router(name="places")


def places_view(user_id: int, deleting: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    items = saved.list(user_id)
    if deleting:
        rows = [[InlineKeyboardButton(text=f"❌ {p.name}"[:60], callback_data=f"pl:rm:{i}")]
                for i, p in enumerate(items)]
        rows.append([InlineKeyboardButton(text="↩️ Готово", callback_data="pl:list")])
        return "Нажмите место, которое нужно удалить:", InlineKeyboardMarkup(inline_keyboard=rows)
    rows = [[InlineKeyboardButton(text=f"📍 {p.name}"[:60], callback_data=build_cb(1, p.lat, p.lon))]
            for p in items]
    actions = [InlineKeyboardButton(text="➕ Добавить", callback_data="pl:add")]
    if items:
        actions.append(InlineKeyboardButton(text="🗑 Удалить", callback_data="pl:del"))
    if len(items) >= 2:
        actions.append(InlineKeyboardButton(text="📊 Сравнить", callback_data="pl:cmp"))
    rows.append(actions)
    if items:
        text = "⭐ Мои места:\n" + "\n".join(f"{i}. {fmt_place(p)}" for i, p in enumerate(items, 1))
    else:
        text = "⭐ Список мест пуст. Нажмите «➕ Добавить» или используйте /add <i>город</i>"
    return text, InlineKeyboardMarkup(inline_keyboard=rows)



# ---------- Мои места ----------

async def save_place(m: Message, user_id: int, place: Place):
    result = saved.add(user_id, place)
    text = {
        "added": f"✅ Добавлено: {fmt_place(place)}",
        "updated": f"✅ Обновлено: {fmt_place(place)}",
        "exists": f"Уже есть в ваших местах: {fmt_place(place)}",
        "full": f"В списке уже {FAV_LIMIT} мест — удалите лишнее через /places",
    }[result]
    await m.answer(text, reply_markup=open_places_markup())


async def ask_place(m: Message, state: FSMContext):
    await state.set_state(Input.place)
    await m.answer(ASK_PLACE, reply_markup=cancel_markup())


@router.message(Input.place, INPUT_TEXT, flags=KEEP_INPUT)
async def place_input(m: Message, state: FSMContext):
    """Ответ на «Отправьте название города…»: город или координаты."""
    uid = m.from_user.id
    await state.clear()
    if not await with_place(m, uid, m.text, lambda target, place: save_place(target, uid, place)):
        await state.set_state(Input.place)  # не нашлось — даём попробовать ещё раз


@router.message(Input.place, F.location, flags=KEEP_INPUT)
async def place_location(m: Message, state: FSMContext):
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
        await m.answer("Не понял координаты. Пример: <code>/add 51.18 32.83 Дача</code> "
                       "(широта от -90 до 90, долгота от -180 до 180)")
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
        await m.answer("Список мест пуст.", reply_markup=open_places_markup())
        return
    if not key:
        text, markup = places_view(uid, deleting=True)
        await m.answer(text, reply_markup=markup)
        return
    removed = saved.remove_by(uid, key)
    if removed:
        await m.answer(f"🗑 Удалено: {fmt_place(removed)}", reply_markup=open_places_markup())
    else:
        await m.answer(f"Не нашёл «{escape(key)}» в ваших местах. Номера — в /places")


@router.message(F.text == BTN_PLACES)
async def btn_places(m: Message):
    await places_cmd(m)


@router.callback_query(F.data.startswith("pl:"))
async def on_places_button(cb: CallbackQuery, state: FSMContext):
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, откройте /places", show_alert=True)
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
    if action.startswith("rm:"):
        removed = saved.remove(uid, int(action[3:])) if action[3:].isdigit() else None
        await cb.answer(f"Удалено: {removed.name}" if removed else "Уже удалено")
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
        _, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    name = place_name(cb.from_user.id, lat, lon)
    place = Place(coords_name(lat, lon) if name == DEFAULT_NAME else name, lat, lon)
    result = saved.add(cb.from_user.id, place)
    await cb.answer({"added": f"⭐ Добавлено: {place.name}", "updated": "⭐ Обновлено",
                     "exists": "Уже есть в ваших местах",
                     "full": f"В списке уже {FAV_LIMIT} мест"}[result], show_alert=result == "full")



async def send_compare(m: Message, user_id: int):
    items = saved.list(user_id)
    if len(items) < 2:
        await m.answer("Для сравнения нужно хотя бы два места в «⭐ Мои места» — добавьте их через /add",
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
    series = [(p.name, d["daily"]["time"], d["daily"]["temperature_2m_max"], d["daily"]["temperature_2m_min"])
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



