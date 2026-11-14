"""Роутер dates: погода на выбранную дату — /date, календарь, ввод даты текстом."""
import asyncio
import logging
from datetime import date, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
from astro import astro_text
from charts import hourly_chart, wind_humidity_chart
from core import (BTN_DATE, INPUT_TEXT, KEEP_INPUT, NO_PLACE, Input, cancel_markup, keyboard, last_places,
                  norm_line, place_data, place_from, place_name, send_album, with_place)
from dates import (build_cal_cb, build_date_cb, calendar_days, date_source, parse_cal_cb, parse_date,
                   parse_date_cb, source_error, split_date_args)
from places import build_cb
from weather import DAYS_RU, Place, format_day

router = Router(name="dates")

def day_markup(day: date, place: Place) -> InlineKeyboardMarkup:
    prev_day, next_day = day - timedelta(days=1), day + timedelta(days=1)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"◀ {prev_day:%d.%m}", callback_data=build_date_cb(prev_day, place.lat, place.lon)),
         InlineKeyboardButton(text=f"{next_day:%d.%m} ▶", callback_data=build_date_cb(next_day, place.lat, place.lon))],
        [InlineKeyboardButton(text="📆 Другая дата", callback_data=build_cal_cb("f", place.lat, place.lon)),
         InlineKeyboardButton(text="⭐ В мои места", callback_data=f"fa:{place.lat:.3f}:{place.lon:.3f}")],
        [InlineKeyboardButton(text="🌤 Сейчас", callback_data=build_cb(1, place.lat, place.lon))],
    ])


def calendar_markup(page: str, place: Place) -> InlineKeyboardMarkup:
    today = date.today()
    buttons = [InlineKeyboardButton(text="Сегодня" if d == today else f"{DAYS_RU[d.weekday()]} {d:%d.%m}",
                                    callback_data=build_date_cb(d, place.lat, place.lon))
               for d in calendar_days(page, today)]
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    switch = ("◀ Прошлые дни", "p") if page == "f" else ("Ближайшие дни ▶", "f")
    rows.append([InlineKeyboardButton(text=switch[0], callback_data=build_cal_cb(switch[1], place.lat, place.lon)),
                 InlineKeyboardButton(text="✏️ Ввести дату", callback_data=build_cal_cb("i", place.lat, place.lon))])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def render_day_charts(name: str, data: dict, day: date) -> list[bytes]:
    label = f"{DAYS_RU[day.weekday()]} {day:%d.%m.%Y}"
    return [hourly_chart(name, data, title=f"{name}: {label}, по часам"),
            wind_humidity_chart(name, data, 1, title=f"{name}: ветер и влажность, {label}")]



async def send_day(m: Message, place: Place, day: date, user_id: int):
    """Погода за выбранную дату: прогноз (до +15 дней) или архив (раньше недели назад)."""
    src = date_source(day, date.today())
    if source_error(src):
        await m.answer(source_error(src), reply_markup=calendar_markup("f", place))
        return
    archive = src == "archive"
    try:
        data = await core.client.fetch_day(place, day, archive)
    except Exception:
        logging.exception("weather day error")
        await m.answer("Не удалось получить погоду за эту дату, попробуйте чуть позже 🙏")
        return
    last_places.set(user_id, place)
    text = format_day(place.name, data, day, archive)
    line = await norm_line(place, day, data.get("daily") or {})
    if line:
        text += "\n" + line
    try:
        text += "\n\n" + astro_text(place.lat, place.lon, data, next_phases_line=False)
    except Exception:
        logging.exception("astro error")
    try:
        pngs = await asyncio.to_thread(render_day_charts, place.name, data, day)
    except Exception:
        logging.exception("chart error")
        pngs = None
    await send_album(m, text, pngs, day_markup(day, place),
                     f"📍 {escape(place.name)} — {DAYS_RU[day.weekday()]} {day:%d.%m.%Y}")



# ---------- Выбор даты ----------

async def show_calendar(m: Message, place: Place | None, page: str = "f"):
    if not place:
        await m.answer(NO_PLACE, reply_markup=keyboard)
        return
    title = "Прошлые дни" if page == "p" else "Выберите дату"
    await m.answer(f"📆 {title} — {escape(place.name)}", reply_markup=calendar_markup(page, place))


@router.message(Command("date"))
async def date_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    if not (command.args or "").strip():
        await show_calendar(m, last_places.get(uid))
        return
    day, query = split_date_args(command.args, date.today())
    if not day:
        await m.answer("Не понял дату. Примеры: <code>/date 21.11</code>, <code>/date 21.11.2026 Казань</code>, "
                       "<code>/date завтра</code>, <code>/date вчера 51.18, 32.83</code>")
        return
    if query.strip():
        await with_place(m, uid, query, lambda target, place: send_day(target, place, day, uid))
        return
    place = last_places.get(uid)
    if not place:
        await m.answer(NO_PLACE, reply_markup=keyboard)
        return
    await send_day(m, place, day, uid)


@router.message(F.text == BTN_DATE)
async def btn_date(m: Message):
    await show_calendar(m, last_places.get(m.from_user.id))


@router.callback_query(F.data.startswith("c:"))
async def on_calendar_button(cb: CallbackQuery, state: FSMContext):
    parsed = parse_cal_cb(cb.data)
    if not parsed or not isinstance(cb.message, Message):
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    await cb.answer()
    page, lat, lon = parsed
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    if page == "i":
        await state.set_state(Input.date)
        await state.set_data(place_data(place))
        await cb.message.answer("Напишите дату: <code>21.11</code>, <code>21.11.2026</code>, "
                                "<code>завтра</code> или <code>вчера</code>", reply_markup=cancel_markup())
        return
    title = "Прошлые дни" if page == "p" else "Выберите дату"
    try:
        await cb.message.edit_text(f"📆 {title} — {escape(place.name)}", reply_markup=calendar_markup(page, place))
    except Exception:
        await show_calendar(cb.message, place, page)


@router.callback_query(F.data.startswith("d:"))
async def on_date_button(cb: CallbackQuery):
    parsed = parse_date_cb(cb.data)
    if not parsed or not isinstance(cb.message, Message):
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    day, lat, lon = parsed
    await cb.answer()
    await send_day(cb.message, Place(place_name(cb.from_user.id, lat, lon), lat, lon), day, cb.from_user.id)





@router.message(Input.date, INPUT_TEXT, flags=KEEP_INPUT)
async def date_input(m: Message, state: FSMContext):
    """Ответ на «Напишите дату» после кнопки календаря «✏️ Ввести дату»."""
    place = place_from(await state.get_data())
    day = parse_date(m.text, date.today())
    if not day:  # состояние остаётся — можно попробовать ещё раз
        await m.answer("Не понял дату, попробуйте так: <code>21.11</code> или <code>21.11.2026</code>",
                       reply_markup=cancel_markup())
        return
    await state.clear()
    await send_day(m, place, day, m.from_user.id)
