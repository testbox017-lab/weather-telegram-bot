"""Погодный Telegram-бот. Запуск: python bot.py (токен в .env)"""
import asyncio
import itertools
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from html import escape

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from collections.abc import Awaitable, Callable
from aiogram.types import (BotCommand, BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, Message,
                           ReplyKeyboardMarkup)

from air import format_air
from alerts import ALERT_LIMIT, CHECK_EVERY, KINDS, Alerts, check_all
from astro import astro_text
from charts import compare_chart, daily_chart, hourly_chart, wind_humidity_chart
from dates import (build_cal_cb, build_date_cb, calendar_days, date_source, parse_cal_cb, parse_date,
                   parse_date_cb, source_error, split_date_args)
from places import (DEFAULT_NAME, FAV_LIMIT, Favorites, LastPlaces, build_cb, coords_name, parse_cb,
                    parse_coords)
from subs import (MAX_TIMES, SUB_LIMIT, Subscriptions, condition_met, describe as describe_sched,
                  describe_cond, local_time, parse_schedule, run_due, split_condition, split_place_schedule,
                  split_short)
import health
from normals import Normals, norm_text
from weather import (ARCHIVE_URL, DAYS_RU, FORECAST_URL, GEO_URL, Place, WeatherClient, format_day,
                     format_forecast, format_hourly, format_short)
from weekend import compare_text, format_weekend

router = Router()
client: WeatherClient  # создаётся в main()

def load_env_file(path: Path = Path(__file__).with_name(".env")) -> None:
    """Читает KEY=VALUE из .env рядом с bot.py (не перезаписывает уже заданные переменные)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()  # до создания хранилищ: DATA_DIR может быть задан в .env
DATA_DIR = Path(os.getenv("DATA_DIR") or Path(__file__).parent)
DATA_DIR.mkdir(parents=True, exist_ok=True)
last_places = LastPlaces(DATA_DIR / "last_places.json")
saved = Favorites(DATA_DIR / "saved_places.json")
subs = Subscriptions(DATA_DIR / "subscriptions.json")
alerts = Alerts(DATA_DIR / "alerts.json")
normals = Normals(DATA_DIR / "normals.json")
waiting: dict[int, tuple[str, Place | None]] = {}  # ждём от пользователя место ("add") или дату ("date")
PlaceAction = Callable[[Message, Place], Awaitable[None]]
choices: dict[int, tuple[int, list[Place], PlaceAction]] = {}  # выбор среди одноимённых городов
choice_ids = itertools.count(1)

BTN_GEO = "📍 Моя геолокация"
BTN_NOW = "🌤 Погода сейчас"
BTN_WEEK = "📅 Прогноз на неделю"
BTN_HELP = "❓ Помощь"
BTN_PLACES = "⭐ Мои места"
BTN_DATE = "📆 Выбрать дату"
BTN_SUBS = "🔔 Рассылка"
BTN_PING = "📡 Связь"
BTN_ALERTS = "⚠️ Предупреждения"
NO_PLACE = "Напишите название города или нажмите «📍 Моя геолокация»"
ASK_PLACE = ("Отправьте название города, координаты (например <code>51.18, 32.83</code>) "
             "или геолокацию — добавлю в «Мои места»")

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_GEO, request_location=True), KeyboardButton(text=BTN_NOW)],
        [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_DATE)],
        [KeyboardButton(text=BTN_PLACES), KeyboardButton(text=BTN_SUBS), KeyboardButton(text=BTN_ALERTS)],
        [KeyboardButton(text=BTN_PING), KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

HELP = (
    "Я показываю погоду 🌦\n\n"
    "• Просто напишите название города, например <i>Москва</i>, пришлю погоду, "
    "графики на сутки (температура, осадки, ветер, влажность), восход и заход солнца и луны, фазу луны\n"
    "• /week <i>город</i> то же на 7 дней\n"
    "• Или отправьте геолокацию кнопкой ниже\n\n"
    "Кнопки внизу:\n"
    f"• {BTN_GEO} — погода там, где вы сейчас\n"
    f"• {BTN_NOW} и {BTN_WEEK} — для последнего города или места\n"
    "• Под прогнозом: 🔄 Обновить (перерисует тот же прогноз), переключение сегодня/неделя и ⏱ По часам — "
    "12 часов текстом\n"
    "• В сводке есть совет, что надеть 👕\n"
    "/weather и /week без города тоже показывают последнее место\n"
    "• Координаты текстом, например <code>51.18, 32.83</code>, — погода в этой точке\n"
    "• Если городов с таким названием несколько, предложу выбрать кнопками. Можно сразу уточнить "
    "через запятую: <i>Бахмач, Черниговская</i> или <i>Париж, США</i>\n\n"
    f"{BTN_PLACES} — ваш список мест (до {FAV_LIMIT}):\n"
    "• /add <i>город</i> или /add <i>широта долгота [название]</i> — добавить\n"
    "• /places — список, нажмите место, чтобы узнать погоду\n"
    "• /del <i>номер или название</i> — удалить\n"
    "• ⭐ В мои места — кнопка под прогнозом\n\n"
    f"{BTN_DATE} — погода на любую дату (прогноз до 16 дней вперёд, архив с 1940 года):\n"
    "• /date <i>21.11</i> или <i>21.11.2026</i>, <i>завтра</i>, <i>вчера</i> [город или координаты]\n"
    "• 📆 Другая дата — кнопка под прогнозом\n\n"
    f"{BTN_SUBS} — бот сам присылает погоду (до {SUB_LIMIT} рассылок):\n"
    "• /subscribe [город] — выбрать периодичность: каждый 1/3/6/12 ч, раз в сутки или в своё время\n"
    "• /subscribe <i>Бахмач 3ч</i> или <i>Бахмач 08:00, 20:00</i> — сразу\n"
    "• добавьте <i>кратко</i> — три строки без графиков (переключается и в /subs)\n"
    "• дни недели: <i>Бахмач по будням 07:30</i>, <i>сб вс 10:00</i>\n"
    "• условие: <i>Бахмач 07:00 если дождь</i> (снег, мороз, ниже -5, выше 25) — "
    "без осадков рассылка в этот день не придёт\n"
    "• /subs — ваши рассылки, /unsubscribe <i>номер</i> или <i>all</i> — отключить\n"
    "• 🔔 Подписаться — кнопка под прогнозом\n\n"
    f"{BTN_ALERTS} или /alerts — бот сам напишет, если ожидается заморозок, гроза, порывы ветра от 15 м/с, "
    "жара, сильный мороз, резкий перепад температуры или осадки через 1–2 часа (ночью с 23 до 7 молчит). "
    f"До {ALERT_LIMIT} мест, каждое предупреждение включается отдельно\n\n"
    "Ещё:\n"
    "• /air [город] или 🌫 Воздух под прогнозом — качество воздуха (индекс EAQI, PM2.5, PM10) и пыльца\n"
    "• /weekend [город] или 🏖 Выходные — прогноз на ближайшие субботу и воскресенье с советом\n"
    "• /compare или 📊 Сравнить в «Моих местах» — все места в одном сообщении и на одном графике\n"
    "• В сводке на сегодня и на дату есть строка 📈 «как обычно в этот день» — норма за 1991–2020\n\n"
    f"{BTN_PING} или /ping — проверить связь: сервер бота, Telegram, Open-Meteo, рассылки"
)


def fmt_place(p: Place) -> str:
    return f"{escape(p.name)} ({p.lat:.2f}, {p.lon:.2f})"


def place_name(user_id: int, lat: float, lon: float) -> str:
    i = saved.find(user_id, lat, lon)
    return saved.list(user_id)[i].name if i is not None else last_places.name_for(user_id, lat, lon)


def forecast_markup(days: int, place: Place) -> InlineKeyboardMarkup:
    other = (7, "📅 Неделя") if days == 1 else (1, "🌤 Сегодня")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="r" + build_cb(days, place.lat, place.lon)[1:]),
         InlineKeyboardButton(text=other[1], callback_data=build_cb(other[0], place.lat, place.lon))],
        [InlineKeyboardButton(text="⭐ В мои места", callback_data=f"fa:{place.lat:.3f}:{place.lon:.3f}"),
         InlineKeyboardButton(text="📆 Другая дата", callback_data=build_cal_cb("f", place.lat, place.lon))],
        [InlineKeyboardButton(text="⏱ По часам", callback_data=f"hr:{place.lat:.3f}:{place.lon:.3f}"),
         InlineKeyboardButton(text="🔔 Подписаться", callback_data=f"sb:{place.lat:.3f}:{place.lon:.3f}")],
        [InlineKeyboardButton(text="🌫 Воздух", callback_data=f"aq:{place.lat:.3f}:{place.lon:.3f}"),
         InlineKeyboardButton(text="🏖 Выходные", callback_data=f"we:{place.lat:.3f}:{place.lon:.3f}")],
        [InlineKeyboardButton(text="⚠️ Предупреждения", callback_data=f"al:new:{place.lat:.3f}:{place.lon:.3f}")],
    ])


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


def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✖️ Отмена", callback_data="x")]])


def open_places_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Мои места", callback_data="pl:list")]])


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


@router.message(CommandStart())
async def start(m: Message):
    waiting.pop(m.from_user.id, None)
    await m.answer(f"Привет, {escape(m.from_user.first_name or '')}! 👋\n\n{HELP}", reply_markup=keyboard)


@router.message(Command("help"))
async def help_cmd(m: Message):
    waiting.pop(m.from_user.id, None)
    await m.answer(HELP, reply_markup=keyboard)


def render_charts(name: str, data: dict, days: int) -> list[bytes]:
    """Температура/осадки + ветер/влажность (почасово на сутки или по дням)."""
    main_chart = daily_chart(name, data) if days > 1 else hourly_chart(name, data)
    return [main_chart, wind_humidity_chart(name, data, days)]


def render_day_charts(name: str, data: dict, day: date) -> list[bytes]:
    label = f"{DAYS_RU[day.weekday()]} {day:%d.%m.%Y}"
    return [hourly_chart(name, data, title=f"{name}: {label}, по часам"),
            wind_humidity_chart(name, data, 1, title=f"{name}: ветер и влажность, {label}")]


# (chat_id, id сообщения с кнопками) → id фотографий альбома над ним: для «🔄 Обновить» на месте
album_ids: dict[tuple[int, int], list[int]] = {}
ALBUM_MEMORY = 300


def _album_media(text: str, pngs: list[bytes]) -> list[InputMediaPhoto]:
    fits = len(text) <= 1024
    return [InputMediaPhoto(media=BufferedInputFile(png, filename=f"weather{i}.png"),
                            caption=text if i == 0 and fits else None)
            for i, png in enumerate(pngs)]


async def send_album(m: Message, text: str, pngs: list[bytes] | None, markup, short: str):
    """Альбом с подписью-текстом; кнопки — отдельным коротким сообщением (альбом их не несёт)."""
    if not pngs:
        await m.answer(text, reply_markup=markup)
        return
    photos = await m.answer_media_group(_album_media(text, pngs))
    buttons = await m.answer(short if len(text) <= 1024 else text, reply_markup=markup)
    try:
        album_ids[(buttons.chat.id, buttons.message_id)] = [p.message_id for p in photos]
        while len(album_ids) > ALBUM_MEMORY:
            album_ids.pop(next(iter(album_ids)))
    except AttributeError:  # подменённые сообщения в тестах
        pass


_norm_tasks: dict[str, asyncio.Task] = {}


async def norm_line(place: Place, day: date | None, daily: dict, wait: float = 6) -> str | None:
    """Строка «как обычно в этот день». Первый расчёт для места долгий (архив за 30 лет):
    ждём не дольше wait секунд, дальше расчёт докачивается в фоне и пригодится в следующий раз."""
    if day is None:
        return None
    norm = normals.cached(place.lat, place.lon)
    if norm is None:
        from normals import place_key

        key = place_key(place.lat, place.lon)
        task = _norm_tasks.get(key)
        if task is None or task.done():
            task = _norm_tasks[key] = asyncio.create_task(normals.load(client, place.lat, place.lon))
        try:
            norm = await asyncio.wait_for(asyncio.shield(task), wait)
        except asyncio.TimeoutError:
            return None
        except Exception:
            logging.exception("normals error")
            return None
    tmax, tmin = (daily.get("temperature_2m_max") or [None])[0], (daily.get("temperature_2m_min") or [None])[0]
    return norm_text(norm, day, tmax, tmin)


async def build_weather(place: Place, days: int, header: str = "", data: dict | None = None):
    """Данные для ответа: (data, текст, картинки или None, короткая подпись для сообщения с кнопками)."""
    if data is None:
        data = await client.fetch(place, days)
    text = header + format_forecast(place.name, data, days)
    if days == 1:
        line = await norm_line(place, date.fromisoformat(data["daily"]["time"][0]) if data.get("daily") else None,
                               data.get("daily") or {})
        if line:
            text += "\n" + line
    try:
        text += "\n\n" + astro_text(place.lat, place.lon, data)
    except Exception:
        logging.exception("astro error")
    try:
        pngs = await asyncio.to_thread(render_charts, place.name, data, days)
    except Exception:
        logging.exception("chart error")
        pngs = None
    period = "на сегодня" if days == 1 else "на 7 дней"
    return data, text, pngs, f"📍 {escape(place.name)} — прогноз {period}"


async def send_weather(m, place: Place, days: int, user_id: int | None = None, header: str = "",
                       data: dict | None = None):
    """Текст прогноза (+ солнце и луна), альбом из двух графиков и inline-кнопки."""
    _, text, pngs, short = await build_weather(place, days, header, data)
    if user_id is not None:
        last_places.set(user_id, place)
    await send_album(m, text, pngs, forecast_markup(days, place), short)


async def refresh_weather(msg: Message, place: Place, days: int, user_id: int) -> bool:
    """Перерисовать прогноз в тех же сообщениях. False — не получилось (старое сообщение и т. п.)."""
    ids = album_ids.get((msg.chat.id, msg.message_id))
    data, text, pngs, short = await build_weather(place, days)
    last_places.set(user_id, place)
    stamp = (data.get("current") or {}).get("time", "")[11:16]
    stamp = f"\n<i>обновлено в {stamp} по местному времени</i>" if stamp else ""
    markup = forecast_markup(days, place)
    if not pngs and not ids:  # прогноз без картинок: всё в одном сообщении
        await msg.edit_text(text + stamp, reply_markup=markup)
        return True
    if not pngs or not ids or len(ids) != len(pngs):
        return False
    for mid, media in zip(ids, _album_media(text, pngs)):
        await msg.bot.edit_message_media(media=media, chat_id=msg.chat.id, message_id=mid)
    await msg.edit_text((short if len(text) <= 1024 else text) + stamp, reply_markup=markup)
    return True


async def send_day(m: Message, place: Place, day: date, user_id: int):
    """Погода за выбранную дату: прогноз (до +15 дней) или архив (раньше недели назад)."""
    src = date_source(day, date.today())
    if source_error(src):
        await m.answer(source_error(src), reply_markup=calendar_markup("f", place))
        return
    archive = src == "archive"
    try:
        data = await client.fetch_day(place, day, archive)
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


async def reply_for_place(m: Message, place: Place, days: int, user_id: int):
    try:
        await send_weather(m, place, days, user_id)
    except Exception:
        logging.exception("weather error")
        await m.answer("Не удалось получить погоду, попробуйте чуть позже 🙏")


async def reply_for_last(m: Message, days: int):
    place = last_places.get(m.from_user.id)
    if not place:
        await m.answer(NO_PLACE, reply_markup=keyboard)
        return
    await reply_for_place(m, place, days, m.from_user.id)


def choice_markup(choice_id: int, places: list[Place]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📍 {p.name}"[:64], callback_data=f"pk:{choice_id}:{i}")]
            for i, p in enumerate(places)]
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="x")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def with_place(m: Message, user_id: int, query: str, action: PlaceAction) -> bool:
    """Координаты или название города → action(target, place).

    Если одноимённых мест несколько, показывает кнопки и выполняет action после выбора.
    Возвращает False, если место не нашлось (пользователю уже сказано).
    """
    query = query.strip()
    coords = parse_coords(query)
    if coords:
        lat, lon, name = coords
        await action(m, Place(name or coords_name(lat, lon), lat, lon))
        return True
    try:
        places, obvious = await client.find_cities(query)
    except Exception:
        logging.exception("geocoding error")
        await m.answer("Не удалось найти место, попробуйте чуть позже 🙏")
        return False
    if not places:
        await m.answer(f"Не нашёл город «{escape(query)}» 🤷 Проверьте написание.")
        return False
    if obvious:
        await action(m, places[0])
        return True
    choice_id = next(choice_ids)
    choices[user_id] = (choice_id, places, action)
    await m.answer(f"🔎 Нашёл несколько мест «{escape(query)}». Какое нужно?",
                   reply_markup=choice_markup(choice_id, places))
    return True


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


async def ask_place(m: Message, user_id: int):
    waiting[user_id] = ("add", None)
    await m.answer(ASK_PLACE, reply_markup=cancel_markup())


@router.message(Command("add"))
async def add_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    waiting.pop(uid, None)
    query = (command.args or "").strip()
    if not query:
        await ask_place(m, uid)
        return
    if query.split(maxsplit=1)[0].replace(".", "").replace(",", "").lstrip("-+").isdigit() \
            and not parse_coords(query):
        await m.answer("Не понял координаты. Пример: <code>/add 51.18 32.83 Дача</code> "
                       "(широта от -90 до 90, долгота от -180 до 180)")
        return
    await with_place(m, uid, query, lambda target, place: save_place(target, uid, place))


@router.message(Command("places"))
async def places_cmd(m: Message):
    waiting.pop(m.from_user.id, None)
    text, markup = places_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.message(Command("del"))
async def del_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    waiting.pop(uid, None)
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
async def on_places_button(cb: CallbackQuery):
    if not isinstance(cb.message, Message):
        await cb.answer("Сообщение устарело, откройте /places", show_alert=True)
        return
    uid, action = cb.from_user.id, cb.data[3:]
    if action == "add":
        await cb.answer()
        await ask_place(cb.message, uid)
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


@router.callback_query(F.data == "x")
async def on_cancel(cb: CallbackQuery):
    waiting.pop(cb.from_user.id, None)
    choices.pop(cb.from_user.id, None)
    await cb.answer("Отменено")
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text("Отменено.")
        except Exception:
            pass


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
    waiting.pop(uid, None)
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
    waiting.pop(m.from_user.id, None)
    await show_calendar(m, last_places.get(m.from_user.id))


@router.callback_query(F.data.startswith("c:"))
async def on_calendar_button(cb: CallbackQuery):
    parsed = parse_cal_cb(cb.data)
    if not parsed or not isinstance(cb.message, Message):
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    await cb.answer()
    page, lat, lon = parsed
    place = Place(place_name(cb.from_user.id, lat, lon), lat, lon)
    if page == "i":
        waiting[cb.from_user.id] = ("date", place)
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


# ---------- Рассылка по расписанию ----------

class ChatTarget:
    """Минимальная замена Message для отправки без входящего сообщения (рассылка)."""

    def __init__(self, bot: Bot, chat_id: int):
        self.bot, self.chat_id = bot, chat_id

    async def answer(self, text: str, reply_markup=None):
        return await self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    async def answer_media_group(self, media):
        return await self.bot.send_media_group(self.chat_id, media)


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
        tz = await client.timezone(place)
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
    waiting.pop(uid, None)
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
    waiting.pop(m.from_user.id, None)
    text, markup = subs_view(m.from_user.id)
    await m.answer(text, reply_markup=markup)


@router.message(F.text == BTN_SUBS)
async def btn_subs(m: Message):
    await subs_cmd(m)


@router.message(Command("unsubscribe"))
async def unsubscribe_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    waiting.pop(uid, None)
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
async def on_schedule_button(cb: CallbackQuery):
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
        waiting[cb.from_user.id] = ("sub", place)
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


async def scheduler(bot: Bot, every: float = 30):
    """Фоновая задача: раз в `every` секунд отправляет наступившие рассылки."""
    logging.info("scheduler started: %d subscriptions", sum(len(v) for v in subs._data.values()))

    async def send(uid: int, sub: dict):
        place = Subscriptions.place(sub)
        data = await client.fetch(place, 1)
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
    waiting.pop(uid, None)
    query = (command.args or "").strip()
    if query:
        await with_place(m, uid, query, lambda target, place: show_alert_setup(target, uid, place))
        return
    text, markup = alerts_view(uid)
    await m.answer(text, reply_markup=markup)


@router.message(F.text == BTN_ALERTS)
async def btn_alerts(m: Message):
    waiting.pop(m.from_user.id, None)
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
            n = await check_all(alerts, lambda p: client.fetch(p, 2), send, datetime.now(timezone.utc),
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
    async with client.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
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
    waiting.pop(m.from_user.id, None)
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


# ---------- Воздух, выходные, сравнение мест ----------

async def for_city(m: Message, query: str, action: PlaceAction):
    """Город из команды или, если его нет, последнее место пользователя."""
    query = (query or "").strip()
    if query:
        await with_place(m, m.from_user.id, query, action)
        return
    place = last_places.get(m.from_user.id)
    if not place:
        await m.answer(NO_PLACE, reply_markup=keyboard)
        return
    await action(m, place)


def back_markup(place: Place) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🌤 Сейчас", callback_data=build_cb(1, place.lat, place.lon)),
        InlineKeyboardButton(text="📅 Неделя", callback_data=build_cb(7, place.lat, place.lon))]])


async def send_air(m: Message, place: Place):
    try:
        data = await client.fetch_air(place)
    except Exception:
        logging.exception("air error")
        await m.answer("Не удалось получить данные о воздухе, попробуйте чуть позже 🙏")
        return
    await m.answer(format_air(escape(place.name), data), reply_markup=back_markup(place))


async def send_weekend(m: Message, place: Place):
    try:
        data = await client.fetch(place, 7)
    except Exception:
        logging.exception("weekend error")
        await m.answer("Не удалось получить прогноз, попробуйте чуть позже 🙏")
        return
    await m.answer(format_weekend(escape(place.name), data), reply_markup=back_markup(place))


async def send_compare(m: Message, user_id: int):
    items = saved.list(user_id)
    if len(items) < 2:
        await m.answer("Для сравнения нужно хотя бы два места в «⭐ Мои места» — добавьте их через /add",
                       reply_markup=open_places_markup())
        return

    async def one(p: Place):
        try:
            return await client.fetch(p, 7)
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


@router.message(Command("air"))
async def air_cmd(m: Message, command: CommandObject):
    waiting.pop(m.from_user.id, None)
    await for_city(m, command.args, send_air)


@router.message(Command("weekend"))
async def weekend_cmd(m: Message, command: CommandObject):
    waiting.pop(m.from_user.id, None)
    await for_city(m, command.args, send_weekend)


@router.message(Command("compare"))
async def compare_cmd(m: Message):
    waiting.pop(m.from_user.id, None)
    await send_compare(m, m.from_user.id)


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
    waiting.pop(m.from_user.id, None)
    await reply_for_city(m, command.args or "", 7)


@router.message(Command("weather"))
async def weather_cmd(m: Message, command: CommandObject):
    waiting.pop(m.from_user.id, None)
    await reply_for_city(m, command.args or "", 1)


@router.message(F.location)
async def by_location(m: Message):
    uid, loc = m.from_user.id, m.location
    state = waiting.pop(uid, None)
    if state and state[0] == "add":
        await save_place(m, uid, Place(coords_name(loc.latitude, loc.longitude), loc.latitude, loc.longitude))
        return
    place = Place("Ваше местоположение", loc.latitude, loc.longitude)
    await reply_for_place(m, place, 1, uid)


@router.message(F.text == BTN_NOW)
async def btn_now(m: Message):
    waiting.pop(m.from_user.id, None)
    await reply_for_last(m, 1)


@router.message(F.text == BTN_WEEK)
async def btn_week(m: Message):
    waiting.pop(m.from_user.id, None)
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
        data = await client.fetch(place, 1)
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
    uid = m.from_user.id
    state = waiting.pop(uid, None)
    if state and state[0] == "add":
        if not await with_place(m, uid, m.text, lambda target, place: save_place(target, uid, place)):
            waiting[uid] = state  # даём попробовать ещё раз
        return
    if state and state[0] == "sub":
        sched = parse_schedule(m.text)
        if not sched or "times" not in sched:
            waiting[uid] = state
            await m.answer(f"Не понял время. Пример: <code>07:30</code> или <code>08:00, 20:00</code> "
                           f"(не больше {MAX_TIMES})", reply_markup=cancel_markup())
            return
        await create_sub(m, uid, state[1], sched)
        return
    if state and state[0] == "date":
        day = parse_date(m.text, date.today())
        if not day:
            waiting[uid] = state
            await m.answer("Не понял дату, попробуйте так: <code>21.11</code> или <code>21.11.2026</code>",
                           reply_markup=cancel_markup())
            return
        await send_day(m, state[1], day, uid)
        return
    await reply_for_city(m, m.text, 1)


async def main():
    global client
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Не найден BOT_TOKEN: создайте файл .env рядом с bot.py со строкой BOT_TOKEN=ваш_токен")
    bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать и показать кнопки"),
            BotCommand(command="weather", description="Погода сейчас: /weather Город"),
            BotCommand(command="week", description="Прогноз на неделю: /week Город"),
            BotCommand(command="date", description="Погода на дату: /date 21.11 Город"),
            BotCommand(command="places", description="Мои места"),
            BotCommand(command="add", description="Добавить место: /add Город или /add 51.18 32.83"),
            BotCommand(command="del", description="Удалить место: /del номер или название"),
            BotCommand(command="subscribe", description="Рассылка погоды: /subscribe Город 3ч"),
            BotCommand(command="subs", description="Мои рассылки"),
            BotCommand(command="unsubscribe", description="Отключить рассылку: /unsubscribe номер|all"),
            BotCommand(command="alerts", description="Предупреждения: заморозок, гроза, ветер"),
            BotCommand(command="air", description="Качество воздуха и пыльца: /air Город"),
            BotCommand(command="weekend", description="Погода на выходные: /weekend Город"),
            BotCommand(command="compare", description="Сравнить мои места"),
            BotCommand(command="ping", description="Проверить связь с сервером"),
            BotCommand(command="help", description="Справка"),
        ])
    except Exception:
        logging.exception("set_my_commands error")
    async with aiohttp.ClientSession() as session:
        client = WeatherClient(session)
        tasks = [asyncio.create_task(scheduler(bot)), asyncio.create_task(alert_checker(bot))]
        try:
            await dp.start_polling(bot)
        finally:
            for task in tasks:
                task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
