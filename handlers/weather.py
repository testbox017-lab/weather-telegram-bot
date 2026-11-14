"""Роутер weather: погода сейчас и на неделю, по часам, обновление, воздух, выходные,
а также общее — /start, /help, выбор среди одноимённых городов, «Отмена» и город текстом.
Подключается последним: его обработчик текста ловит всё, что не забрали другие роутеры."""
import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
from air import format_air
from core import (BTN_HELP, BTN_NOW, BTN_WEEK, HELP, back_markup, choices, for_city, keyboard, place_name,
                  refresh_weather, reply_for_last, reply_for_place, with_place)
from places import build_cb, parse_cb
from weather import Place, format_hourly
from weekend import format_weekend

router = Router(name="weather")


@router.message(CommandStart())
async def start(m: Message):
    await m.answer(f"Привет, {escape(m.from_user.first_name or '')}! 👋\n\n{HELP}", reply_markup=keyboard)


@router.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(HELP, reply_markup=keyboard)



@router.callback_query(F.data.startswith("pk:"))
async def on_choice_button(cb: CallbackQuery):
    try:
        _, choice_id, index = cb.data.split(":")
        choice_id, index = int(choice_id), int(index)
    except ValueError:
        choice_id, index = 0, 0
    pending = choices.get(cb.from_user.id)
    if not pending or pending[0] != choice_id or not 0 <= index < len(pending[1]) \
            or not isinstance(cb.message, Message):
        await cb.answer("Этот список устарел — напишите название ещё раз", show_alert=True)
        return
    choices.pop(cb.from_user.id, None)
    place, action = pending[1][index], pending[2]
    await cb.answer()
    try:
        await cb.message.edit_text(f"📍 {escape(place.name)}")
    except Exception:
        pass
    await action(cb.message, place)


async def reply_for_city(m: Message, query: str, days: int):
    query = query.strip()
    if not query:
        await reply_for_last(m, days)
        return
    uid = m.from_user.id

    async def show(target: Message, place: Place):
        await reply_for_place(target, place, days, uid)

    await with_place(m, uid, query, show)



@router.callback_query(F.data == "x")
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    choices.pop(cb.from_user.id, None)
    await cb.answer("Отменено")
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text("Отменено.")
        except Exception:
            pass



async def send_air(m: Message, place: Place):
    try:
        data = await core.client.fetch_air(place)
    except Exception:
        logging.exception("air error")
        await m.answer("Не удалось получить данные о воздухе, попробуйте чуть позже 🙏")
        return
    await m.answer(format_air(escape(place.name), data), reply_markup=back_markup(place))


async def send_weekend(m: Message, place: Place):
    try:
        data = await core.client.fetch(place, 7)
    except Exception:
        logging.exception("weekend error")
        await m.answer("Не удалось получить прогноз, попробуйте чуть позже 🙏")
        return
    await m.answer(format_weekend(escape(place.name), data), reply_markup=back_markup(place))



@router.message(Command("air"))
async def air_cmd(m: Message, command: CommandObject):
    await for_city(m, command.args, send_air)


@router.message(Command("weekend"))
async def weekend_cmd(m: Message, command: CommandObject):
    await for_city(m, command.args, send_weekend)



@router.callback_query(F.data.regexp(r"^(aq|we):"))
async def on_air_weekend_button(cb: CallbackQuery):
    try:
        kind, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, запросите прогноз заново", show_alert=True)
        return
    await cb.answer()
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    await (send_air if kind == "aq" else send_weekend)(cb.message, place)


# ---------- Общие кнопки и ввод ----------

@router.message(Command("week"))
async def week(m: Message, command: CommandObject):
    await reply_for_city(m, command.args or "", 7)


@router.message(Command("weather"))
async def weather_cmd(m: Message, command: CommandObject):
    await reply_for_city(m, command.args or "", 1)


@router.message(F.location)
async def by_location(m: Message):
    """Геолокация — погода в этой точке (для «Моих мест» её перехватывает роутер places)."""
    loc = m.location
    await reply_for_place(m, Place("Ваше местоположение", loc.latitude, loc.longitude), 1, m.from_user.id)


@router.message(F.text == BTN_NOW)
async def btn_now(m: Message):
    await reply_for_last(m, 1)


@router.message(F.text == BTN_WEEK)
async def btn_week(m: Message):
    await reply_for_last(m, 7)


@router.message(F.text == BTN_HELP)
async def btn_help(m: Message):
    await help_cmd(m)


@router.callback_query(F.data.startswith("hr:"))
async def on_hourly_button(cb: CallbackQuery):
    """«⏱ По часам»: ближайшие 12 часов текстом, без картинок."""
    try:
        _, lat, lon = cb.data.split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, запросите прогноз заново", show_alert=True)
        return
    await cb.answer()
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    try:
        data = await core.client.fetch(place, 1)
    except Exception:
        logging.exception("hourly error")
        await cb.message.answer("Не удалось получить погоду, попробуйте чуть позже 🙏")
        return
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🌤 Сейчас", callback_data=build_cb(1, lat, lon))]])
    await cb.message.answer(format_hourly(escape(place.name), data), reply_markup=back)


@router.callback_query(F.data.startswith("r:"))
async def on_refresh_button(cb: CallbackQuery):
    """«🔄 Обновить»: тот же прогноз в тех же сообщениях, без нового сообщения."""
    parsed = parse_cb("w" + cb.data[1:])
    if not parsed or not isinstance(cb.message, Message):
        await cb.answer("Кнопка устарела, запросите прогноз заново", show_alert=True)
        return
    days, lat, lon = parsed
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    try:
        done = await refresh_weather(cb.message, place, days, cb.from_user.id)
    except Exception as e:
        if "message is not modified" in str(e):
            await cb.answer("Уже актуально")
            return
        logging.exception("refresh error")
        done = False
    if done:
        await cb.answer("🔄 Обновлено")
        return
    await cb.answer()
    await reply_for_place(cb.message, place, days, cb.from_user.id)


@router.callback_query(F.data.startswith("w:"))
async def on_forecast_button(cb: CallbackQuery):
    parsed = parse_cb(cb.data)
    if not parsed or not isinstance(cb.message, Message):
        await cb.answer("Кнопка устарела, запросите прогноз заново", show_alert=True)
        return
    await cb.answer()
    days, lat, lon = parsed
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    await reply_for_place(cb.message, place, days, cb.from_user.id)


@router.message(F.text & ~F.text.startswith("/"))
async def by_text(m: Message):
    """Название города или координаты текстом. Ответы на вопросы бота (место, дата, время рассылки)
    сюда не доходят: их забирают обработчики состояний в роутерах places, dates и subs."""
    await reply_for_city(m, m.text, 1)
