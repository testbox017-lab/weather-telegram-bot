"""Выбор среди одноимённых городов в bot.py (без Telegram: подменяем сообщения и геокодер)."""
import os
import tempfile

import pytest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
import bot  # noqa: E402
from weather import Place  # noqa: E402

A, B = Place("Бахмач, Черниговская область, Украина", 51.18, 32.83), Place("Бахмач, Сумская область, Украина", 50.9, 34.1)


class FakeMessage:
    def __init__(self):
        self.sent, self.edited = [], []

    async def answer(self, text, reply_markup=None):
        self.sent.append((text, reply_markup))

    async def edit_text(self, text, reply_markup=None):
        self.edited.append(text)


class FakeClient:
    def __init__(self, places, obvious):
        self.result = (places, obvious)

    async def find_cities(self, query):
        return self.result


class FakeUser:
    id = 42


class FakeCallback:
    def __init__(self, data, message):
        self.data, self.message, self.from_user, self.alerts = data, message, FakeUser(), []

    async def answer(self, text=None, show_alert=False):
        self.alerts.append(text)


@pytest.fixture
def chosen(monkeypatch):
    got = []

    async def action(target, place):
        got.append(place)

    monkeypatch.setattr(bot, "isinstance", lambda o, t: True, raising=False)  # FakeMessage вместо Message
    return got, action


@pytest.mark.asyncio
async def test_obvious_place_runs_at_once(monkeypatch, chosen):
    got, action = chosen
    monkeypatch.setattr(bot, "client", FakeClient([A], True), raising=False)
    m = FakeMessage()
    assert await bot.with_place(m, 42, "Бахмач", action)
    assert got == [A] and not m.sent


@pytest.mark.asyncio
async def test_coords_skip_geocoder(monkeypatch, chosen):
    got, action = chosen
    monkeypatch.setattr(bot, "client", None, raising=False)
    assert await bot.with_place(FakeMessage(), 42, "51.18, 32.83 Дача", action)
    assert got == [Place("Дача", 51.18, 32.83)]


@pytest.mark.asyncio
async def test_not_found(monkeypatch, chosen):
    got, action = chosen
    monkeypatch.setattr(bot, "client", FakeClient([], False), raising=False)
    m = FakeMessage()
    assert not await bot.with_place(m, 42, "Абырвалг", action)
    assert not got and "Не нашёл" in m.sent[0][0]


@pytest.mark.asyncio
async def test_choice_then_button(monkeypatch, chosen):
    got, action = chosen
    monkeypatch.setattr(bot, "client", FakeClient([A, B], False), raising=False)
    m = FakeMessage()
    assert await bot.with_place(m, 42, "Бахмач", action)
    assert not got
    text, markup = m.sent[0]
    buttons = [row[0] for row in markup.inline_keyboard]
    assert "несколько" in text and [b.text for b in buttons[:2]] == [f"📍 {A.name}", f"📍 {B.name}"]

    await bot.on_choice_button(FakeCallback(buttons[1].callback_data, m))
    assert got == [B] and m.edited == [f"📍 {B.name}"]

    cb = FakeCallback(buttons[0].callback_data, m)  # повторное нажатие — список уже использован
    await bot.on_choice_button(cb)
    assert got == [B] and cb.alerts and "устарел" in cb.alerts[0]


class FakeChat:
    id = 7


class FakeBot:
    def __init__(self):
        self.edited_media = []

    async def edit_message_media(self, media, chat_id, message_id):
        self.edited_media.append((chat_id, message_id, media.caption))


class ButtonsMessage(FakeMessage):
    def __init__(self, message_id=12):
        super().__init__()
        self.chat, self.message_id, self.bot = FakeChat(), message_id, FakeBot()
        self.markups = []

    async def edit_text(self, text, reply_markup=None):
        self.edited.append(text)
        self.markups.append(reply_markup)


@pytest.mark.asyncio
async def test_refresh_edits_album_in_place(monkeypatch):
    async def fake_build(place, days, header=""):
        return {"current": {"time": "2026-11-14T15:45"}}, "прогноз", [b"png1", b"png2"], "📍 коротко"

    monkeypatch.setattr(bot, "build_weather", fake_build)
    msg = ButtonsMessage()
    bot.album_ids[(7, 12)] = [10, 11]
    assert await bot.refresh_weather(msg, A, 1, 42)
    assert [(c, m) for c, m, _ in msg.bot.edited_media] == [(7, 10), (7, 11)]
    assert msg.bot.edited_media[0][2] == "прогноз"
    assert msg.edited == ["📍 коротко\n<i>обновлено в 15:45 по местному времени</i>"]
    refresh = msg.markups[0].inline_keyboard[0][0]
    assert refresh.callback_data.startswith("r:1:")


@pytest.mark.asyncio
async def test_refresh_unknown_message_falls_back(monkeypatch):
    async def fake_build(place, days, header=""):
        return {}, "прогноз", [b"png1", b"png2"], "коротко"

    monkeypatch.setattr(bot, "build_weather", fake_build)
    assert not await bot.refresh_weather(ButtonsMessage(99), A, 1, 42)
