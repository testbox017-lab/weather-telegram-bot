"""Общее для всех роутеров: настройки, хранилища, клиент Open-Meteo, кнопки меню, ожидание ввода (FSM)
и помощники, которыми пользуются несколько роутеров (выбор места, отправка прогноза)."""
import asyncio
import itertools
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date
from html import escape
from pathlib import Path

from aiogram import BaseMiddleware, Bot, F
from aiogram.dispatcher.flags import get_flag
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
                           KeyboardButton, Message, ReplyKeyboardMarkup)

from alerts import ALERT_LIMIT, Alerts
from astro import astro_text
from charts import daily_chart, hourly_chart, wind_humidity_chart
from dates import build_cal_cb
from normals import Normals, norm_text
from places import FAV_LIMIT, Favorites, LastPlaces, build_cb, coords_name, parse_coords
from prefs import Prefs, current_user, model_label
from subs import SUB_LIMIT, Subscriptions
from weather import Place, WeatherClient, format_forecast

client: WeatherClient  # создаётся в bot.main(); в других модулях — только через core.client


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
prefs = Prefs(DATA_DIR / "prefs.json")
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
BTN_SETTINGS = "⚙️ Настройки"
NO_PLACE = "Напишите название города или нажмите «📍 Моя геолокация»"
ASK_PLACE = ("Отправьте название города, координаты (например <code>51.18, 32.83</code>) "
             "или геолокацию — добавлю в «Мои места»")

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_GEO, request_location=True), KeyboardButton(text=BTN_NOW)],
        [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_DATE)],
        [KeyboardButton(text=BTN_PLACES), KeyboardButton(text=BTN_SUBS), KeyboardButton(text=BTN_ALERTS)],
        [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_PING), KeyboardButton(text=BTN_HELP)],
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
    "• /table [город] или 📋 Таблица — 3 дня текстом: утро, день, вечер и ночь\n"
    "• /compare или 📊 Сравнить в «Моих местах» — все места в одном сообщении и на одном графике\n"
    "• В сводке на сегодня и на дату есть строка 📈 «как обычно в этот день» — норма за 1991–2020\n\n"
    f"{BTN_SETTINGS} или /settings — модель прогноза (Авто, ECMWF, ICON, GFS) и источник качества воздуха "
    "(Open-Meteo, станции WAQI или выключено)\n\n"
    f"{BTN_PING} или /ping — проверить связь: сервер бота, Telegram, Open-Meteo, рассылки"
)


# ---------- Ожидание ввода (FSM) ----------

class Input(StatesGroup):
    """Чего бот ждёт от пользователя следующим сообщением."""
    place = State()     # место для «Моих мест»: город, координаты или геолокация
    date = State()      # дата для места из данных состояния
    sub_time = State()  # время рассылки для места из данных состояния


MENU_BUTTONS = (BTN_GEO, BTN_NOW, BTN_WEEK, BTN_HELP, BTN_PLACES, BTN_DATE, BTN_SUBS, BTN_PING, BTN_ALERTS,
                BTN_SETTINGS)
# Текст, который считается ответом на вопрос бота: не команда и не кнопка меню
INPUT_TEXT = F.text & ~F.text.startswith("/") & ~F.text.in_(MENU_BUTTONS)
KEEP_INPUT = {"keep_input": True}  # флаг обработчиков ввода: состояние они ведут сами


class CurrentUserMiddleware(BaseMiddleware):
    """Запоминает, чьё сообщение или кнопка обрабатывается (prefs.current_user): по нему клиент
    Open-Meteo берёт модель прогноза, а кнопки — источник качества воздуха."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        token = current_user.set(user.id if user else None)
        try:
            return await handler(event, data)
        finally:
            current_user.reset(token)


class ResetInputMiddleware(BaseMiddleware):
    """Любой другой обработчик сообщения (команда, кнопка меню, геолокация, город текстом)
    отменяет ожидание ввода — как раньше waiting.pop() в начале каждого обработчика."""

    async def __call__(self, handler, event, data):
        state = data.get("state")
        if state is not None and not get_flag(data, "keep_input"):
            if await state.get_state() is not None:
                await drop_prompt(data.get("bot"), event.chat.id, state)
            await state.clear()
        return await handler(event, data)


async def send_prompt(m: Message, state, text: str) -> None:
    """Вопрос с кнопкой «✖️ Отмена»; прежний вопрос теряет свою кнопку, чтобы в чате не висели старые «Отмена»."""
    await drop_prompt(m.bot, m.chat.id, state)
    sent = await m.answer(text, reply_markup=cancel_markup())
    await state.update_data(prompt=sent.message_id)


async def drop_prompt(bot: Bot | None, chat_id: int, state) -> None:
    """Убрать кнопку «Отмена» у последнего вопроса (ввод получен, отменён или задан заново)."""
    prompt = (await state.get_data()).get("prompt")
    if not prompt or bot is None:
        return
    await state.update_data(prompt=None)
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=prompt, reply_markup=None)
    except Exception:  # сообщение удалено или уже без кнопок
        pass


def short_name(name: str) -> str:
    """«Бахмач, Черниговская область, Украина» → «Бахмач» (для кнопок и легенд)."""
    return name.split(",")[0].strip() or name


def place_data(place: Place) -> dict:
    return {"place": asdict(place)}


def place_from(data: dict) -> Place | None:
    p = data.get("place")
    return Place(p["name"], p["lat"], p["lon"]) if p else None


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
         InlineKeyboardButton(text="🏖 Выходные", callback_data=f"we:{place.lat:.3f}:{place.lon:.3f}")]
        if prefs.current()["air"] != "off" else  # качество воздуха выключено в /settings
        [InlineKeyboardButton(text="🏖 Выходные", callback_data=f"we:{place.lat:.3f}:{place.lon:.3f}")],
        [InlineKeyboardButton(text="📋 Таблица", callback_data=f"tb:{place.lat:.3f}:{place.lon:.3f}"),
         InlineKeyboardButton(text="⚠️ Предупреждения", callback_data=f"al:new:{place.lat:.3f}:{place.lon:.3f}")],
    ])



def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✖️ Отмена", callback_data="x")]])


def open_places_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Мои места", callback_data="pl:list")]])



def render_charts(name: str, data: dict, days: int) -> list[bytes]:
    """Температура/осадки + ветер/влажность (почасово на сутки или по дням)."""
    main_chart = daily_chart(name, data) if days > 1 else hourly_chart(name, data)
    return [main_chart, wind_humidity_chart(name, data, days)]



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
    model = prefs.current()["model"]
    if model != "best_match":
        text += f"\n<i>Модель прогноза: {model_label(model)}</i>"
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



# ---------- Рассылка по расписанию ----------

class ChatTarget:
    """Минимальная замена Message для отправки без входящего сообщения (рассылка)."""

    def __init__(self, bot: Bot, chat_id: int):
        self.bot, self.chat_id = bot, chat_id

    async def answer(self, text: str, reply_markup=None):
        return await self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    async def answer_media_group(self, media):
        return await self.bot.send_media_group(self.chat_id, media)



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



