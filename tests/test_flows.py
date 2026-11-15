"""Сценарии с ожиданием ввода через настоящий диспетчер aiogram (роутеры, FSM, middleware).

Telegram подменён сессией, которая записывает запросы бота, Open-Meteo — FakeClient.
"""
import os
import tempfile
from datetime import date, datetime, timezone

import pytest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
from aiogram import Bot  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, GetMe, SendMediaGroup  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Location, Message, Update, User  # noqa: E402

import bot as entry  # noqa: E402
import core  # noqa: E402
from core import BTN_NOW, Input  # noqa: E402
from dates import build_cal_cb  # noqa: E402
from handlers import dates as dates_router, subs as subs_router, weather as weather_router  # noqa: E402
from weather import Place  # noqa: E402

UID = 4242
USER = User(id=UID, is_bot=False, first_name="Dmitry")
CHAT = Chat(id=UID, type="private")
DP = entry.build_dispatcher()  # роутеры подключаются к диспетчеру один раз
BAKHMACH = Place("Бахмач, Черниговская область, Украина", 51.18, 32.83)


class FakeSession(BaseSession):
    """Вместо HTTP к Telegram: запоминает методы и отвечает правдоподобными объектами."""

    def __init__(self):
        super().__init__()
        self.calls, self._id = [], 1000

    def _msg(self, text=None):
        self._id += 1
        return Message(message_id=self._id, date=datetime.now(timezone.utc), chat=CHAT, text=text)

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="bot", username="test_bot")
        if isinstance(method, SendMediaGroup):
            return [self._msg() for _ in method.media]
        if hasattr(method, "chat_id"):
            return self._msg(getattr(method, "text", None))
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def close(self):
        pass

    def texts(self):
        return [m.text for m in self.calls if getattr(m, "text", None)]


class FakeClient:
    async def find_cities(self, query):
        return ([BAKHMACH], True) if query.startswith("Бахмач") else ([], False)

    async def timezone(self, place):
        return "Europe/Kyiv"


@pytest.fixture
def tg(monkeypatch, tmp_path):
    for name, cls in (("saved", core.Favorites), ("last_places", core.LastPlaces), ("subs", core.Subscriptions),
                      ("prefs", core.Prefs)):
        store = cls(tmp_path / f"{name}.json")
        monkeypatch.setattr(core, name, store)
        for mod in (dates_router, subs_router, weather_router, entry.places, entry.settings):
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, store)
    monkeypatch.setattr(core, "client", FakeClient(), raising=False)
    session = FakeSession()
    tg_bot = Bot("42:TEST", session=session)
    dp = DP
    dp.fsm.storage = MemoryStorage()  # каждый тест — с чистым состоянием
    n = iter(range(1, 10_000))

    async def send(text=None, location=None):
        msg = Message(message_id=next(n), date=datetime.now(timezone.utc), chat=CHAT, from_user=USER, text=text,
                      location=Location(latitude=location[0], longitude=location[1]) if location else None)
        await dp.feed_update(tg_bot, Update(update_id=next(n), message=msg))

    async def press(data):
        msg = Message(message_id=next(n), date=datetime.now(timezone.utc), chat=CHAT, text="кнопки")
        cb = CallbackQuery(id=str(next(n)), from_user=USER, chat_instance="ci", data=data, message=msg)
        await dp.feed_update(tg_bot, Update(update_id=next(n), callback_query=cb))

    async def state():
        return await dp.fsm.get_context(tg_bot, chat_id=UID, user_id=UID).get_state()

    class T:
        pass

    t = T()
    t.send, t.press, t.state, t.session = send, press, state, session
    return t


@pytest.fixture
def recorded(monkeypatch):
    """Подменяет отправку погоды: проверяем маршрутизацию, а не графики."""
    got = []

    async def city(m, query, days):
        got.append(("city", query, days))

    async def last(m, days):
        got.append(("last", days))

    async def day(m, place, d, user_id):
        got.append(("day", place, d))

    monkeypatch.setattr(weather_router, "reply_for_city", city)
    monkeypatch.setattr(weather_router, "reply_for_last", last)
    monkeypatch.setattr(dates_router, "send_day", day)
    return got


@pytest.mark.asyncio
async def test_add_place_retry_then_saved(tg, recorded):
    await tg.send("/add")
    assert await tg.state() == Input.place.state
    await tg.send("Абырвалг")  # не нашлось — бот ждёт дальше
    assert "Не нашёл" in tg.session.texts()[-1]
    assert await tg.state() == Input.place.state
    await tg.send("Бахмач")
    assert [p.name for p in core.saved.list(UID)] == [BAKHMACH.name]
    assert await tg.state() is None
    assert not recorded  # текст ушёл в «Мои места», а не в погоду


@pytest.mark.asyncio
async def test_add_place_by_location(tg):
    await tg.press("pl:add")
    await tg.send(location=(50.45, 30.52))
    assert [(p.lat, p.lon) for p in core.saved.list(UID)] == [(50.45, 30.52)]
    assert await tg.state() is None


@pytest.mark.asyncio
async def test_menu_button_cancels_input(tg, recorded):
    await tg.send("/add")
    await tg.send(BTN_NOW)
    assert recorded == [("last", 1)] and await tg.state() is None
    await tg.send("Бахмач")  # теперь это просто город
    assert recorded[-1] == ("city", "Бахмач", 1) and not core.saved.list(UID)


@pytest.mark.asyncio
async def test_known_command_cancels_unknown_keeps(tg, recorded):
    await tg.send("/add")
    await tg.send("/nosuchcommand")  # неизвестную команду бот не обрабатывает — ожидание остаётся
    assert await tg.state() == Input.place.state
    await tg.send("/places")
    assert await tg.state() is None


@pytest.mark.asyncio
async def test_location_while_waiting_for_date_shows_weather(tg, monkeypatch):
    got = []

    async def fake_reply(m, place, days, user_id):
        got.append(place.name)

    monkeypatch.setattr(weather_router, "reply_for_place", fake_reply)
    await tg.press(build_cal_cb("i", 51.18, 32.83))
    await tg.send(location=(51.18, 32.83))
    assert got == ["Ваше местоположение"] and await tg.state() is None


@pytest.mark.asyncio
async def test_date_input(tg, recorded):
    await tg.press(build_cal_cb("i", 51.18, 32.83))
    assert await tg.state() == Input.date.state and "Напишите дату" in tg.session.texts()[-1]
    await tg.send("тридцатое февраля")
    assert "Не понял дату" in tg.session.texts()[-1] and await tg.state() == Input.date.state
    await tg.send("21.11")
    kind, place, day = recorded[-1]
    assert kind == "day" and (place.lat, place.lon) == (51.18, 32.83)
    assert (day.day, day.month) == (21, 11) and day >= date.today().replace(day=1, month=1)
    assert await tg.state() is None


@pytest.mark.asyncio
async def test_cancel_button(tg, recorded):
    await tg.press(build_cal_cb("i", 51.18, 32.83))
    await tg.press("x")
    assert await tg.state() is None
    await tg.send("21.11")
    assert recorded == [("city", "21.11", 1)]


@pytest.mark.asyncio
async def test_custom_subscription_time(tg):
    await tg.press("si:0:51.180:32.830")
    assert await tg.state() == Input.sub_time.state
    await tg.send("полвосьмого")
    assert "Не понял время" in tg.session.texts()[-1] and await tg.state() == Input.sub_time.state
    await tg.send("07:30")
    items = core.subs.list(UID)
    assert len(items) == 1 and items[0]["sched"]["times"] == ["07:30"]
    assert "Рассылка включена" in tg.session.texts()[-1] and await tg.state() is None


@pytest.mark.asyncio
async def test_retry_removes_old_cancel_button(tg, recorded):
    await tg.press(build_cal_cb("i", 51.18, 32.83))
    first = tg.session._id  # «Напишите дату» с кнопкой «Отмена»
    await tg.send("абв")
    await tg.send("21.11")
    dropped = [c.message_id for c in tg.session.calls if isinstance(c, EditMessageReplyMarkup)]
    assert len(dropped) == 2 and dropped[0] == first < dropped[1]  # первый вопрос, потом повторный


@pytest.mark.asyncio
async def test_menu_button_drops_prompt(tg, recorded):
    await tg.send("/add")
    await tg.send(BTN_NOW)
    assert any(isinstance(c, EditMessageReplyMarkup) for c in tg.session.calls)


@pytest.mark.asyncio
async def test_delete_place_asks_confirmation(tg):
    core.saved.add(UID, BAKHMACH)
    await tg.press("pl:ask:0")
    ask = [c for c in tg.session.calls if isinstance(c, EditMessageText)][-1]
    assert "Удалить «Бахмач" in ask.text and core.saved.list(UID)
    await tg.press("pl:rm:0")
    assert not core.saved.list(UID)


@pytest.mark.asyncio
async def test_new_subscription_asks_place(tg):
    core.saved.add(UID, BAKHMACH)
    core.saved.add(UID, Place("Нежин, Черниговская область, Украина", 51.05, 31.89))
    await tg.press("su:new")
    assert "Для какого места" in tg.session.texts()[-1]
    buttons = [b.text for row in tg.session.calls[-1].reply_markup.inline_keyboard for b in row]
    assert any("Бахмач" in t for t in buttons) and any("Нежин" in t for t in buttons)


@pytest.mark.asyncio
async def test_subs_buttons_use_short_names(tg):
    core.subs.add(UID, BAKHMACH, {"hours": 12}, "Europe/Kyiv", datetime.now(timezone.utc))
    await tg.send("/subs")
    buttons = [b.text for row in tg.session.calls[-1].reply_markup.inline_keyboard for b in row]
    assert "❌ 1. Бахмач — каждые 12 ч" in buttons


@pytest.mark.asyncio
async def test_settings_choose_model_and_air(tg):
    await tg.send("/settings")
    assert "✅ <b>Авто</b>" in tg.session.texts()[-1]
    await tg.press("cfg:model:ecmwf_ifs025")
    await tg.press("cfg:air:off")
    p = core.prefs.get(UID)
    assert (p["model"], p["air"]) == ("ecmwf_ifs025", "off")
    edited = [c for c in tg.session.calls if isinstance(c, EditMessageText)][-1]
    assert "✅ <b>ECMWF</b>" in edited.text and "✅ <b>Выключено</b>" in edited.text
    await tg.press("cfg:model:nonsense")
    assert core.prefs.get(UID)["model"] == "ecmwf_ifs025"


@pytest.mark.asyncio
async def test_air_off_hides_button_and_command(tg):
    from prefs import current_user

    core.prefs.set(UID, "air", "off")
    await tg.press("aq:51.180:32.830")
    assert "Качество воздуха выключено" in tg.session.texts()[-1]
    token = current_user.set(UID)
    try:
        buttons = [b.text for row in core.forecast_markup(1, BAKHMACH).inline_keyboard for b in row]
    finally:
        current_user.reset(token)
    assert "🌫 Воздух" not in buttons and "🏖 Выходные" in buttons
    assert "🌫 Воздух" in [b.text for row in core.forecast_markup(1, BAKHMACH).inline_keyboard for b in row]


@pytest.mark.asyncio
async def test_handlers_see_current_user_model(tg, monkeypatch):
    """Middleware ставит current_user — клиент Open-Meteo берёт модель пользователя."""
    seen = []

    async def fake_reply(m, place, days, user_id):
        seen.append(core.prefs.current()["model"])

    monkeypatch.setattr(weather_router, "reply_for_place", fake_reply)
    core.prefs.set(UID, "model", "gfs_seamless")
    await tg.send(location=(51.18, 32.83))
    assert seen == ["gfs_seamless"]


@pytest.mark.asyncio
async def test_table_button(tg, monkeypatch):
    from tests.test_table import data as table_data

    asked = []

    async def fetch(place, days):
        asked.append(days)
        return table_data()

    monkeypatch.setattr(core.client, "fetch", fetch, raising=False)
    await tg.press("tb:51.180:32.830")
    assert asked == [4] and "<pre>" in tg.session.texts()[-1]


@pytest.mark.asyncio
async def test_settings_short_fields(tg):
    await tg.press("cfg:short:pressure")
    assert "pressure" in core.prefs.get(UID)["short"]
    edited = [c for c in tg.session.calls if isinstance(c, EditMessageText)][-1]
    assert "✅ Давление" in [b.text for row in edited.reply_markup.inline_keyboard for b in row]


@pytest.mark.asyncio
async def test_models_review_radar_buttons(tg, monkeypatch, tmp_path):
    from aiogram.methods import SendPhoto

    import radar
    from handlers import extras
    from review import ForecastLog
    from tests.test_radar_models_review import models_data, nowcast, past_resp

    monkeypatch.setattr(core, "forecast_log", ForecastLog(tmp_path / "log.json"))

    async def fetch_models(place, models, days):
        return models_data()

    async def fetch_past(place, days):
        return past_resp()

    async def fetch_nowcast(place):
        return nowcast([0, 0.5])

    async def image(session, lat, lon):
        return b"\x89PNG fake", datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)

    for name, fn in (("fetch_models", fetch_models), ("fetch_past", fetch_past), ("fetch_nowcast", fetch_nowcast)):
        monkeypatch.setattr(core.client, name, fn, raising=False)
    monkeypatch.setattr(core.client, "session", None, raising=False)
    monkeypatch.setattr(extras, "radar_image", image)
    await tg.press("md:51.180:32.830")
    assert "что говорят разные модели" in tg.session.texts()[-1]
    await tg.press("rv:51.180:32.830")
    assert "итоги недели" in tg.session.texts()[-1]
    await tg.press("rd:51.180:32.830")
    photo = [c for c in tg.session.calls if isinstance(c, SendPhoto)][-1]
    assert "снимок 08:00" in photo.caption and "начнётся около 10:15" in photo.caption
    assert radar.RING_KM == 50


@pytest.mark.asyncio
async def test_settings_review_toggle(tg):
    await tg.press("cfg:review:off")
    assert core.prefs.get(UID)["review"] == "off"
    assert "ИТОГИ НЕДЕЛИ" in tg.session.texts()[-1]
