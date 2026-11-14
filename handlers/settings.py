"""Роутер settings: настройка предупреждений (/alerts, фоновая alert_checker()) и проверка связи (/ping)."""
import asyncio
import logging
from datetime import datetime, timezone
from html import escape

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
import health
from alerts import ALERT_LIMIT, CHECK_EVERY, KINDS, Alerts, check_all
from core import BTN_ALERTS, BTN_PING, NO_PLACE, alerts, keyboard, last_places, place_name, subs, with_place
from places import build_cb
from weather import ARCHIVE_URL, FORECAST_URL, GEO_URL, Place

router = Router(name="settings")

# ---------- Предупреждения ----------

def alert_setup_view(a: dict) -> tuple[str, InlineKeyboardMarkup]:
    b = InlineKeyboardButton
    kinds = a.get("kinds", [])
    rows = [[b(text=f"{'✅' if k in kinds else '▫️'} {label}", callback_data=f"al:t:{a['id']}:{k}")]
            for k, label in KINDS.items()]
    rows.append([b(text="🗑 Отключить для места", callback_data=f"al:rm:{a['id']}"),
                 b(text="↩️ Все места", callback_data="al:list")])
    on = len(kinds)
    text = (f"⚠️ Предупреждения для «{escape(a['name'])}»: включено {on} из {len(KINDS)}.\n"
            "Нажмите, чтобы включить или выключить. Ночью (23–7 по местному времени) бот молчит.")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def alerts_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = alerts.list(user_id)
    rows = [[InlineKeyboardButton(text=f"⚙️ {a['name']} ({len(a.get('kinds', []))}/{len(KINDS)})"[:60],
                                  callback_data=f"al:open:{a['id']}")] for a in items]
    rows.append([InlineKeyboardButton(text="➕ Для последнего места", callback_data="al:last")])
    if not items:
        return ("⚠️ Предупреждений пока нет. Бот может сам написать, если будет заморозок, гроза, сильный ветер, "
                "жара, мороз, резкий перепад температуры или скоро пойдёт дождь.\n"
                "Включите их кнопкой ниже или «⚠️ Предупреждения» под прогнозом."), \
            InlineKeyboardMarkup(inline_keyboard=rows)
    return "⚠️ Места с предупреждениями (нажмите, чтобы настроить):", InlineKeyboardMarkup(inline_keyboard=rows)


async def show_alert_setup(m: Message, user_id: int, place: Place):
    a = alerts.add(user_id, place)
    if not a:
        await m.answer(f"Предупреждения уже включены для {ALERT_LIMIT} мест — отключите лишнее в /alerts")
        return
    text, markup = alert_setup_view(a)
    await m.answer(text, reply_markup=markup)


@router.message(Command("alerts"))
async def alerts_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    query = (command.args or "").strip()
    if query:
        await with_place(m, uid, query, lambda target, place: show_alert_setup(target, uid, place))
        return
    text, markup = alerts_view(uid)
    await m.answer(text, reply_markup=markup)


@router.message(F.text == BTN_ALERTS)
async def btn_alerts(m: Message):
    text, markup = alerts_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("al:"))
async def on_alerts_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, откройте /alerts", show_alert=True)
        return
    uid, parts = cb.from_user.id, cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    try:
        if action == "new":
            await cb.answer()
            lat, lon = float(parts[2]), float(parts[3])
            await show_alert_setup(cb.message, uid, Place(place_name(uid, lat, lon), lat, lon))
            return
        if action == "last":
            place = last_places.get(uid)
            await cb.answer()
            if not place:
                await cb.message.answer(NO_PLACE, reply_markup=keyboard)
            else:
                await show_alert_setup(cb.message, uid, place)
            return
        if action == "list":
            await cb.answer()
            text, markup = alerts_view(uid)
        elif action == "rm":
            removed = alerts.remove(uid, int(parts[2]))
            await cb.answer(f"Отключено: {removed['name']}" if removed else "Уже отключено")
            text, markup = alerts_view(uid)
        else:  # open / t (переключить вид)
            a = alerts.toggle(uid, int(parts[2]), parts[3]) if action == "t" else alerts.get(uid, int(parts[2]))
            if not a:
                await cb.answer("Уже отключено", show_alert=True)
                return
            await cb.answer()
            text, markup = alert_setup_view(a)
    except (ValueError, IndexError):
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:
        await cb.message.answer(text, reply_markup=markup)


async def alert_checker(bot: Bot):
    """Фоновая проверка предупреждений раз в CHECK_EVERY."""
    logging.info("alerts started: %d places", len(alerts.all()))

    async def send(uid: int, alert: dict, texts: list[str]):
        place = Alerts.place(alert)
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌤 Погода", callback_data=build_cb(1, place.lat, place.lon)),
            InlineKeyboardButton(text="⚙️ Настроить", callback_data=f"al:open:{alert['id']}")]])
        await bot.send_message(uid, f"⚠️ <b>{escape(place.name)}</b>\n" + "\n".join(texts), reply_markup=markup)

    while True:
        try:
            n = await check_all(alerts, lambda p: core.client.fetch(p, 2), send, datetime.now(timezone.utc),
                                (TelegramForbiddenError,))
            if n:
                logging.info("alerts: sent %d", n)
        except Exception:
            logging.exception("alerts error")
        await asyncio.sleep(CHECK_EVERY.total_seconds())


# ---------- Проверка связи ----------

ping_limiter = health.RateLimiter(10)
VERSION = health.bot_version()


def ping_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Проверить снова",
                                                                       callback_data="pg")]])


async def _http(url: str, params: dict) -> str:
    async with core.client.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
        r.raise_for_status()
        await r.read()
        return f"HTTP {r.status}"


async def build_ping_report(tg_bot) -> str:
    async def tg():
        await tg_bot.get_me()

    checks = await asyncio.gather(
        health.measure("Telegram API", tg),
        health.measure("Open-Meteo прогноз", lambda: _http(FORECAST_URL, {
            "latitude": 50.45, "longitude": 30.52, "current": "temperature_2m"})),
        health.measure("Open-Meteo поиск городов", lambda: _http(GEO_URL, {"name": "Kyiv", "count": 1})),
        health.measure("Open-Meteo архив", lambda: _http(ARCHIVE_URL, {
            "latitude": 50.45, "longitude": 30.52, "start_date": "2020-01-01", "end_date": "2020-01-01",
            "daily": "temperature_2m_max"})),
    )
    all_subs = [s for items in subs._data.values() for s in items]
    next_send = min((datetime.fromisoformat(s["next"]) for s in all_subs), default=None)
    return health.format_report(list(checks), datetime.now(timezone.utc), version=VERSION,
                                subs_total=len(all_subs), next_send=next_send, tick=health.last_tick)


async def run_ping(target: Message, user_id: int, edit: bool = False):
    left = ping_limiter.wait_left(user_id)
    if left:
        return f"Подождите {left:.0f} с перед следующей проверкой"
    msg = target if edit else await target.answer("⏳ Проверяю…")
    if edit:
        try:
            await msg.edit_text("⏳ Проверяю…")
        except Exception:
            pass
    try:
        text = await build_ping_report(target.bot)
    except Exception:
        logging.exception("ping error")
        text = "🔴 Не удалось выполнить проверку, попробуйте позже"
    try:
        await msg.edit_text(text, reply_markup=ping_markup())
    except Exception:
        await target.answer(text, reply_markup=ping_markup())
    return None


@router.message(Command("ping", "status"))
async def ping_cmd(m: Message):
    warn = await run_ping(m, m.from_user.id)
    if warn:
        await m.answer(warn)


@router.message(F.text == BTN_PING)
async def btn_ping(m: Message):
    await ping_cmd(m)


@router.callback_query(F.data == "pg")
async def on_ping_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, отправьте /ping", show_alert=True)
        return
    left = ping_limiter.wait_left(cb.from_user.id)
    if left:
        await cb.answer(f"Подождите {left:.0f} с", show_alert=False)
        return
    ping_limiter._last.pop(cb.from_user.id, None)  # разрешение уже проверено выше
    await cb.answer()
    await run_ping(cb.message, cb.from_user.id, edit=True)



