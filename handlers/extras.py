"""Роутер extras: радар осадков (/radar), сравнение моделей (/models), итоги недели (/review)
и фоновая forecast_logger(): каждый вечер записывает прогноз на завтра, по воскресеньям присылает итоги."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
from charts import models_chart
from core import back_markup, for_city, place_name
from places import build_cb
from radar import RING_KM, nowcast_text, radar_image
from review import format_review, key
from spread import SPREAD_MODELS, format_spread, label
from weather import Place

router = Router(name="extras")

LOG_FROM_UTC = 17  # прогноз на завтра записываем вечером: с 19–20 по Киеву
REVIEW_WEEKDAY, REVIEW_FROM_UTC = 6, 18  # итоги недели — в воскресенье с 20:00 по Киеву (зимой)
REVIEW_PLACES = 3


def _markup(kind: str, place: Place, refresh: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text=refresh, callback_data=f"{kind}:{place.lat:.3f}:{place.lon:.3f}")],
        [b(text="🌤 Сейчас", callback_data=build_cb(1, place.lat, place.lon)),
         b(text="📅 Неделя", callback_data=build_cb(7, place.lat, place.lon))]])


# ---------- Радар ----------

async def send_radar(m: Message, place: Place):
    image, nowcast = await asyncio.gather(radar_image(core.client.session, place.lat, place.lon),
                                          core.client.fetch_nowcast(place), return_exceptions=True)
    if isinstance(nowcast, Exception):
        logging.error("nowcast error: %r", nowcast)
        rain = "Прогноз осадков на ближайшие часы сейчас недоступен 🙏"
        offset = 0
    else:
        rain = nowcast_text(nowcast)
        offset = nowcast.get("utc_offset_seconds") or 0
    name = escape(place.name)
    if isinstance(image, Exception):
        logging.error("radar error: %r", image)
        await m.answer(f"🛰 <b>{name}</b>\n{rain}\n\nСнимок радара сейчас недоступен, попробуйте чуть позже 🙏",
                       reply_markup=_markup("rd", place, "🔄 Ещё раз"))
        return
    png, taken = image
    local = taken + timedelta(seconds=offset)
    caption = (f"🛰 <b>{name}</b> — радар осадков, снимок {local:%H:%M}\n{rain}\n\n"
               f"Красная точка — место, круг — {RING_KM} км. Синие и жёлтые пятна — осадки "
               "(чем ярче, тем сильнее). Новый снимок каждые 10 минут.")
    await m.answer_photo(BufferedInputFile(png, "radar.png"), caption=caption,
                         reply_markup=_markup("rd", place, "🔄 Обновить радар"))


# ---------- Сравнение моделей ----------

async def send_models(m: Message, place: Place):
    try:
        data = await core.client.fetch_models(place, SPREAD_MODELS, 7)
        png = await asyncio.to_thread(models_chart, place.name, data, SPREAD_MODELS,
                                      {k: label(k) for k in SPREAD_MODELS})
    except Exception:
        logging.exception("models error")
        await m.answer("Не удалось получить прогноз моделей, попробуйте чуть позже 🙏")
        return
    await m.answer_photo(BufferedInputFile(png, "models.png"))
    await m.answer(format_spread(escape(place.name), data), reply_markup=back_markup(place))


# ---------- Итоги недели ----------

async def review_text(place: Place) -> str:
    past = await core.client.fetch_past(place, 7)
    return format_review(escape(place.name), past, core.forecast_log.forecasts(place), core.forecast_log.first_day())


async def send_review(m: Message, place: Place):
    try:
        text = await review_text(place)
    except Exception:
        logging.exception("review error")
        await m.answer("Не удалось получить погоду за неделю, попробуйте чуть позже 🙏")
        return
    await m.answer(text, reply_markup=back_markup(place))


@router.message(Command("radar"))
async def radar_cmd(m: Message, command: CommandObject):
    await for_city(m, command.args, send_radar)


@router.message(Command("models"))
async def models_cmd(m: Message, command: CommandObject):
    await for_city(m, command.args, send_models)


@router.message(Command("review"))
async def review_cmd(m: Message, command: CommandObject):
    await for_city(m, command.args, send_review)


@router.callback_query(F.data.regexp(r"^(rd|md|rv):"))
async def on_extras_button(cb: CallbackQuery):
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
    await {"rd": send_radar, "md": send_models, "rv": send_review}[kind](cb.message, place)


# ---------- Фон: запись прогнозов и итоги по воскресеньям ----------

def tracked_places() -> list[Place]:
    """Все места из «Моих мест», рассылок и предупреждений всех пользователей, без повторов."""
    out: dict[str, Place] = {}
    for items in core.saved._data.values():
        for p in items:
            out.setdefault(key(float(p["lat"]), float(p["lon"])), Place(p["name"], float(p["lat"]), float(p["lon"])))
    for store in (core.subs, core.alerts):
        for items in store._data.values():
            for s in items:
                if "lat" in s and "lon" in s:
                    out.setdefault(key(float(s["lat"]), float(s["lon"])),
                                   Place(s.get("name") or "Место", float(s["lat"]), float(s["lon"])))
    return list(out.values())


async def log_forecasts(now: datetime, fetch=None, pause: float = 0.5) -> int:
    """Раз в сутки (вечером по UTC) записать прогноз на завтра для каждого места. Возвращает, сколько записано."""
    if now.hour < LOG_FROM_UTC:
        return 0
    fetch = fetch or (lambda p: core.client.fetch(p, 2))
    today, n = now.date().isoformat(), 0
    for place in tracked_places():
        if core.forecast_log.logged_on(place) == today:
            continue
        try:
            data = await fetch(place)
        except Exception:
            logging.exception("forecast log error for %s", place.name)
            continue
        if core.forecast_log.record(place, data, logged=today):
            n += 1
        await asyncio.sleep(pause)
    return n


async def send_reviews(bot: Bot, now: datetime) -> int:
    """В воскресенье вечером — итоги недели тем, у кого они включены в /settings."""
    if now.weekday() != REVIEW_WEEKDAY or now.hour < REVIEW_FROM_UTC:
        return 0
    today, n = now.date().isoformat(), 0
    for uid_s in list(core.saved._data):
        uid = int(uid_s)
        places = core.saved.list(uid)[:REVIEW_PLACES]
        if not places or core.prefs.get(uid)["review"] != "on" or core.forecast_log.sent(uid) == today:
            continue
        core.forecast_log.mark_sent(uid, today)  # и при ошибке: второй раз за вечер не пытаемся
        for place in places:
            try:
                text = await review_text(place)
                await bot.send_message(uid, text, reply_markup=back_markup(place))
                n += 1
            except TelegramForbiddenError:
                break
            except Exception:
                logging.exception("weekly review error")
            await asyncio.sleep(0.3)
    return n


async def forecast_logger(bot: Bot, every: float = 1800):
    while True:
        now = datetime.now(timezone.utc)
        try:
            logged = await log_forecasts(now)
            sent = await send_reviews(bot, now)
            if logged or sent:
                logging.info("forecast log: %d записано, итогов отправлено %d", logged, sent)
        except Exception:
            logging.exception("forecast logger error")
        await asyncio.sleep(every)
