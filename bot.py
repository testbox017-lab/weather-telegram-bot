"""Погодный Telegram-бот. Запуск: python bot.py (токен в .env)"""
import asyncio
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from html import escape

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BotCommand, BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, Message,
                           ReplyKeyboardMarkup)

from astro import astro_text
from charts import daily_chart, hourly_chart, wind_humidity_chart
from dates import (build_cal_cb, build_date_cb, calendar_days, date_source, parse_cal_cb, parse_date,
                   parse_date_cb, source_error, split_date_args)
from places import (DEFAULT_NAME, FAV_LIMIT, Favorites, LastPlaces, build_cb, coords_name, parse_cb,
                    parse_coords)
from weather import DAYS_RU, Place, WeatherClient, format_day, format_forecast

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
waiting: dict[int, tuple[str, Place | None]] = {}  # ждём от пользователя место ("add") или дату ("date")

BTN_GEO = "📍 Моя геолокация"
BTN_NOW = "🌤 Погода сейчас"
BTN_WEEK = "📅 Прогноз на неделю"
BTN_HELP = "❓ Помощь"
BTN_PLACES = "⭐ Мои места"
BTN_DATE = "📆 Выбрать дату"
NO_PLACE = "Напишите название города или нажмите «📍 Моя геолокация»"
ASK_PLACE = ("Отправьте название города, координаты (например <code>51.18, 32.83</code>) "
             "или геолокацию — добавлю в «Мои места»")

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_GEO, request_location=True), KeyboardButton(text=BTN_NOW)],
        [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_HELP)],
        [KeyboardButton(text=BTN_PLACES), KeyboardButton(text=BTN_DATE)],
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
    "• Под прогнозом: 🔄 Обновить и переключение сегодня/неделя\n"
    "/weather и /week без города тоже показывают последнее место\n"
    "• Координаты текстом, например <code>51.18, 32.83</code>, — погода в этой точке\n\n"
    f"{BTN_PLACES} — ваш список мест (до {FAV_LIMIT}):\n"
    "• /add <i>город</i> или /add <i>широта долгота [название]</i> — добавить\n"
    "• /places — список, нажмите место, чтобы узнать погоду\n"
    "• /del <i>номер или название</i> — удалить\n"
    "• ⭐ В мои места — кнопка под прогнозом\n\n"
    f"{BTN_DATE} — погода на любую дату (прогноз до 16 дней вперёд, архив с 1940 года):\n"
    "• /date <i>21.11</i> или <i>21.11.2026</i>, <i>завтра</i>, <i>вчера</i> [город или координаты]\n"
    "• 📆 Другая дата — кнопка под прогнозом"
)


def fmt_place(p: Place) -> str:
    return f"{escape(p.name)} ({p.lat:.2f}, {p.lon:.2f})"


def place_name(user_id: int, lat: float, lon: float) -> str:
    i = saved.find(user_id, lat, lon)
    return saved.list(user_id)[i].name if i is not None else last_places.name_for(user_id, lat, lon)


def forecast_markup(days: int, place: Place) -> InlineKeyboardMarkup:
    other = (7, "📅 Неделя") if days == 1 else (1, "🌤 Сегодня")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=build_cb(days, place.lat, place.lon)),
         InlineKeyboardButton(text=other[1], callback_data=build_cb(other[0], place.lat, place.lon))],
        [InlineKeyboardButton(text="⭐ В мои места", callback_data=f"fa:{place.lat:.3f}:{place.lon:.3f}"),
         InlineKeyboardButton(text="📆 Другая дата", callback_data=build_cal_cb("f", place.lat, place.lon))],
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


async def send_album(m: Message, text: str, pngs: list[bytes] | None, markup, short: str):
    """Альбом с подписью-текстом; кнопки — отдельным коротким сообщением (альбом их не несёт)."""
    if not pngs:
        await m.answer(text, reply_markup=markup)
        return
    fits = len(text) <= 1024
    album = [
        InputMediaPhoto(media=BufferedInputFile(png, filename=f"weather{i}.png"),
                        caption=text if i == 0 and fits else None)
        for i, png in enumerate(pngs)
    ]
    await m.answer_media_group(album)
    await m.answer(short if fits else text, reply_markup=markup)


async def send_weather(m: Message, place: Place, days: int, user_id: int | None = None):
    """Текст прогноза (+ солнце и луна), альбом из двух графиков и inline-кнопки."""
    data = await client.fetch(place, days)
    if user_id is not None:
        last_places.set(user_id, place)
    text = format_forecast(place.name, data, days)
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
    await send_album(m, text, pngs, forecast_markup(days, place),
                     f"📍 {escape(place.name)} — прогноз {period}")


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


async def resolve_place(m: Message, query: str) -> Place | None:
    """Координаты или название города → Place (сообщает пользователю, если не нашлось)."""
    coords = parse_coords(query)
    if coords:
        lat, lon, name = coords
        return Place(name or coords_name(lat, lon), lat, lon)
    try:
        place = await client.find_city(query)
    except Exception:
        logging.exception("geocoding error")
        await m.answer("Не удалось найти место, попробуйте чуть позже 🙏")
        return None
    if not place:
        await m.answer(f"Не нашёл город «{escape(query)}» 🤷 Проверьте написание.")
    return place


async def reply_for_city(m: Message, query: str, days: int):
    query = query.strip()
    if not query:
        await reply_for_last(m, days)
        return
    place = await resolve_place(m, query)
    if place:
        await reply_for_place(m, place, days, m.from_user.id)


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
    place = await resolve_place(m, query)
    if place:
        await save_place(m, uid, place)


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
        place = await resolve_place(m, query.strip())
    else:
        place = last_places.get(uid)
        if not place:
            await m.answer(NO_PLACE, reply_markup=keyboard)
            return
    if place:
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
        place = await resolve_place(m, m.text.strip())
        if place:
            await save_place(m, uid, place)
        else:
            waiting[uid] = state  # даём попробовать ещё раз
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
            BotCommand(command="help", description="Справка"),
        ])
    except Exception:
        logging.exception("set_my_commands error")
    async with aiohttp.ClientSession() as session:
        client = WeatherClient(session)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
