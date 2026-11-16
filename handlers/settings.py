"""Роутер settings: источники данных (/settings), предупреждения (/alerts, фоновая alert_checker())
и проверка связи (/ping)."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from html import escape

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommandScopeChat, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import core
import owm
import health
from alerts import ALERT_LIMIT, CHECK_EVERY, KINDS, Alerts, check_all
from core import (BTN_ALERTS, BTN_PING, BTN_SETTINGS, NO_PLACE, alerts, keyboard, last_places, menu, place_name, prefs,
                  subs, with_place)
from i18n import LANGS, _
from prefs import AIR_SOURCES, CHOICES, MODELS, REVIEW
from weather import SHORT_FIELDS
from places import build_cb
from weather import ARCHIVE_URL, FORECAST_URL, GEO_URL, Place

router = Router(name="settings")

# ---------- Источники данных ----------

def settings_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Как в приложениях погоды: разделы «Погода» и «Качество воздуха», выбранное отмечено галочкой."""
    p = prefs.get(user_id)
    b = InlineKeyboardButton
    lines = [_("⚙️ <b>Настройки</b>"), "",
             "🌐 <b>" + _("ЯЗЫК") + "</b> · " + LANGS[p["lang"]]]
    rows = [[b(text=f"{'✅ ' if p['lang'] == code else ''}{name}", callback_data=f"cfg:lang:{code}")
             for code, name in LANGS.items()]]
    lines += ["", _("<b>ПОГОДА</b> — источник прогноза:")]
    has_owm = bool(owm.api_key())
    for key, (title, about) in MODELS.items():
        if key == owm.KEY and not has_owm and p["model"] != key:
            continue  # без ключа OpenWeatherMap не предлагаем
        title, about = _(title), _(about)
        if not has_owm:
            about = about.replace(_(" (и OpenWeatherMap, если он подключён)"), "")
        mark = "✅ " if p["model"] == key else ""
        lines.append(f"{'✅' if mark else '▫️'} <b>{title}</b> — {about}")
        rows.append([b(text=f"{mark}{title}", callback_data=f"cfg:model:{key}")])
    lines += ["", _("<b>КАЧЕСТВО ВОЗДУХА</b>:")]
    air_row = []
    for key, (title, about) in AIR_SOURCES.items():
        title, about = _(title), _(about)
        mark = "✅ " if p["air"] == key else ""
        lines.append(f"{'✅' if mark else '▫️'} <b>{title}</b> — {about}")
        air_row.append(b(text=f"{mark}{title.split(' · ')[0]}", callback_data=f"cfg:air:{key}"))
    rows.append(air_row)
    lines += ["", _("<b>КРАТКАЯ СВОДКА</b> (рассылки «кратко»): ")
              + ", ".join(_(SHORT_FIELDS[f]).lower() for f in p["short"])]
    short_buttons = [b(text=f"{'✅' if f in p['short'] else '▫️'} {_(title)}", callback_data=f"cfg:short:{f}")
                     for f, title in SHORT_FIELDS.items()]
    rows += [short_buttons[i:i + 2] for i in range(0, len(short_buttons), 2)]
    lines += ["", _("<b>ИТОГИ НЕДЕЛИ</b> — погода за неделю и точность прогноза:")]
    review_row = []
    for key, (title, about) in REVIEW.items():
        title, about = _(title), _(about)
        mark = "✅ " if p["review"] == key else ""
        lines.append(f"{'✅' if mark else '▫️'} <b>{title}</b> — {about}")
        review_row.append(b(text=f"{mark}{title}", callback_data=f"cfg:review:{key}"))
    rows.append(review_row)
    if p["model"] == owm.KEY and not has_owm:
        lines += ["", _("⚠️ Для OpenWeatherMap на сервере не задан ключ — до этого показываю Open-Meteo.")]
    if p["air"] == "waqi" and not os.getenv("WAQI_TOKEN", "").strip():
        lines += ["", _("⚠️ Для WAQI на сервере пока не задан токен — до этого показываю Open-Meteo.")]
    lines += ["", _("Нажмите, чтобы выбрать. Настройка действует на прогнозы, рассылки и предупреждения.")]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def language_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Только выбор языка (/language): подпись на всех трёх языках, чтобы её понял любой."""
    p = prefs.get(user_id)
    rows = [[InlineKeyboardButton(text=f"{'✅ ' if p['lang'] == code else ''}{name}",
                                  callback_data=f"cfg:lang:{code}")] for code, name in LANGS.items()]
    return "🌐 Язык · Мова · Language", InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("settings"))
async def settings_cmd(m: Message):
    text, markup = settings_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.message(menu(BTN_SETTINGS))
async def btn_settings(m: Message):
    await settings_cmd(m)


@router.message(Command("language", "lang"))
async def language_cmd(m: Message):
    text, markup = language_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("cfg:"))
async def on_settings_button(cb: CallbackQuery):
    _prefix, key, value = (cb.data.split(":") + ["", ""])[:3]
    if key == "short":
        if not prefs.toggle_short(cb.from_user.id, value):
            await cb.answer(_("Хотя бы одно поле должно остаться") if value in SHORT_FIELDS else _("Кнопка устарела"),
                            show_alert=True)
            return
        on = value in prefs.get(cb.from_user.id)["short"]
        await cb.answer(_("{field}: показывать", field=_(SHORT_FIELDS[value])) if on
                        else _("{field}: не показывать", field=_(SHORT_FIELDS[value])))
    elif key == "lang":
        old = prefs.get(cb.from_user.id)["lang"]
        if not prefs.set(cb.from_user.id, key, value):
            await cb.answer(_("Кнопка устарела"), show_alert=True)
            return
        await cb.answer(LANGS[value])  # дальше всё — уже на новом языке (prefs.current)
        if value != old and isinstance(cb.message, Message):
            await on_language_changed(cb.message, cb.from_user.id)
    elif not prefs.set(cb.from_user.id, key, value):
        await cb.answer(_("Кнопка устарела"), show_alert=True)
        return
    else:
        await cb.answer(_("Выбрано: {v}", v=_(CHOICES[key][value][0])))
    if isinstance(cb.message, Message):
        short_menu = key == "lang" and cb.message.text and cb.message.text.startswith("🌐")
        text, markup = language_view(cb.from_user.id) if short_menu else settings_view(cb.from_user.id)

        try:
            await cb.message.edit_text(text, reply_markup=markup)
        except Exception:  # «message is not modified» — повторное нажатие
            pass


async def on_language_changed(m: Message, user_id: int):
    """Новый язык: прислать кнопки меню на нём (Telegram меняет их только с новым сообщением)
    и подписи команд в меню «/» для этого чата."""
    await m.answer(_("✅ Язык: {name}. Кнопки внизу — тоже на нём.", name=LANGS[prefs.get(user_id)["lang"]]),
                   reply_markup=keyboard())
    try:
        await m.bot.set_my_commands(core.bot_commands(), scope=BotCommandScopeChat(chat_id=m.chat.id))
    except Exception:
        logging.exception("set_my_commands for chat error")


# ---------- Предупреждения ----------

def alert_setup_view(a: dict) -> tuple[str, InlineKeyboardMarkup]:
    b = InlineKeyboardButton
    kinds = a.get("kinds", [])
    rows = [[b(text=f"{'✅' if k in kinds else '▫️'} {_(label)}", callback_data=f"al:t:{a['id']}:{k}")]
            for k, label in KINDS.items()]
    rows.append([b(text=_("🗑 Отключить для места"), callback_data=f"al:rm:{a['id']}"),
                 b(text=_("↩️ Все места"), callback_data="al:list")])
    on = len(kinds)
    text = _("⚠️ Предупреждения для «{name}»: включено {on} из {total}.\n"
             "Нажмите, чтобы включить или выключить. Ночью (23–7 по местному времени) бот молчит.",
             name=escape(a['name']), on=on, total=len(KINDS))
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def alerts_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = alerts.list(user_id)
    rows = [[InlineKeyboardButton(text=f"⚙️ {a['name']} ({len(a.get('kinds', []))}/{len(KINDS)})"[:60],
                                  callback_data=f"al:open:{a['id']}")] for a in items]
    rows.append([InlineKeyboardButton(text=_("➕ Для последнего места"), callback_data="al:last")])
    if not items:
        return _("⚠️ Предупреждений пока нет. Бот может сам написать, если будет заморозок, гроза, сильный ветер, "
                 "жара, мороз, резкий перепад температуры или скоро пойдёт дождь.\n"
                 "Включите их кнопкой ниже или «⚠️ Предупреждения» под прогнозом."), \
            InlineKeyboardMarkup(inline_keyboard=rows)
    return _("⚠️ Места с предупреждениями (нажмите, чтобы настроить):"), InlineKeyboardMarkup(inline_keyboard=rows)


async def show_alert_setup(m: Message, user_id: int, place: Place):
    a = alerts.add(user_id, place)
    if not a:
        await m.answer(_("Предупреждения уже включены для {n} мест — отключите лишнее в /alerts", n=ALERT_LIMIT))
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


@router.message(menu(BTN_ALERTS))
async def btn_alerts(m: Message):
    text, markup = alerts_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("al:"))
async def on_alerts_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer(_("Сообщение устарело, откройте /alerts"), show_alert=True)
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
                await cb.message.answer(_(NO_PLACE), reply_markup=keyboard())
            else:
                await show_alert_setup(cb.message, uid, place)
            return
        if action == "list":
            await cb.answer()
            text, markup = alerts_view(uid)
        elif action == "rm":
            removed = alerts.remove(uid, int(parts[2]))
            await cb.answer(_("Отключено: {name}", name=removed['name']) if removed else _("Уже отключено"))
            text, markup = alerts_view(uid)
        else:  # open / t (переключить вид)
            a = alerts.toggle(uid, int(parts[2]), parts[3]) if action == "t" else alerts.get(uid, int(parts[2]))
            if not a:
                await cb.answer(_("Уже отключено"), show_alert=True)
                return
            await cb.answer()
            text, markup = alert_setup_view(a)
    except (ValueError, IndexError):
        await cb.answer(_("Кнопка устарела"), show_alert=True)
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
            InlineKeyboardButton(text=_("🌤 Погода"), callback_data=build_cb(1, place.lat, place.lon)),
            InlineKeyboardButton(text=_("⚙️ Настроить"), callback_data=f"al:open:{alert['id']}")]])
        await bot.send_message(uid, f"⚠️ <b>{escape(place.name)}</b>\n" + "\n".join(texts), reply_markup=markup)

    while True:
        try:
            n = await check_all(alerts, lambda p: core.client.fetch(p, 2), send, datetime.now(timezone.utc),
                                (TelegramForbiddenError,), model_of=lambda uid: prefs.get(uid)["model"])
            if n:
                logging.info("alerts: sent %d", n)
        except Exception:
            logging.exception("alerts error")
        await asyncio.sleep(CHECK_EVERY.total_seconds())


# ---------- Проверка связи ----------

ping_limiter = health.RateLimiter(10)
VERSION = health.bot_version()


def ping_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_("🔄 Проверить снова"),
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
        health.measure(_("Open-Meteo прогноз"), lambda: _http(FORECAST_URL, {
            "latitude": 50.45, "longitude": 30.52, "current": "temperature_2m"})),
        health.measure(_("Open-Meteo поиск городов"), lambda: _http(GEO_URL, {"name": "Kyiv", "count": 1})),
        health.measure(_("Open-Meteo архив"), lambda: _http(ARCHIVE_URL, {
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
        return _("Подождите {s:.0f} с перед следующей проверкой", s=left)
    msg = target if edit else await target.answer(_("⏳ Проверяю…"))
    if edit:
        try:
            await msg.edit_text(_("⏳ Проверяю…"))
        except Exception:
            pass
    try:
        text = await build_ping_report(target.bot)
    except Exception:
        logging.exception("ping error")
        text = _("🔴 Не удалось выполнить проверку, попробуйте позже")
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


@router.message(menu(BTN_PING))
async def btn_ping(m: Message):
    await ping_cmd(m)


@router.callback_query(F.data == "pg")
async def on_ping_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer(_("Сообщение устарело, отправьте /ping"), show_alert=True)
        return
    left = ping_limiter.wait_left(cb.from_user.id)
    if left:
        await cb.answer(_("Подождите {s:.0f} с", s=left), show_alert=False)

        return
    ping_limiter._last.pop(cb.from_user.id, None)  # разрешение уже проверено выше
    await cb.answer()
    await run_ping(cb.message, cb.from_user.id, edit=True)



