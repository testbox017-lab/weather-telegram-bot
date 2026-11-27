import io
import json
import zipfile
from datetime import datetime, timezone

import pytest

import databackup
from databackup import due, last_sent, make_zip, mark_sent, owner, send_backup

SUNDAY = datetime(2026, 11, 29, 10, 0, tzinfo=timezone.utc)


def fill(d, users=("42",)):
    (d / "saved_places.json").write_text(json.dumps({u: [] for u in users}), encoding="utf-8")
    (d / "prefs.json").write_text(json.dumps({u: {"lang": "ru"} for u in users}), encoding="utf-8")
    (d / "heartbeat.json").write_text("{}", encoding="utf-8")
    (d / "alerts.json.tmp").write_text("{}", encoding="utf-8")


def test_owner_admin_or_sole_user(tmp_path):
    fill(tmp_path)
    assert owner(tmp_path, {"ADMIN_CHAT_ID": "777"}) == 777
    assert owner(tmp_path, {}) == 42
    fill(tmp_path, users=("1", "2"))
    assert owner(tmp_path, {}) is None
    assert owner(tmp_path / "nope", {}) is None


def test_zip_skips_service_files(tmp_path):
    fill(tmp_path)
    blob, n = make_zip(tmp_path)
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert n == 2 and names == ["prefs.json", "saved_places.json"]
    (tmp_path / "empty").mkdir()
    assert make_zip(tmp_path / "empty")[1] == 0


def test_due_weekly(tmp_path):
    assert due(SUNDAY, None) and not due(SUNDAY.replace(hour=8), None)
    assert not due(SUNDAY.replace(day=28), None)  # суббота
    mark_sent(tmp_path, "2026-11-29")
    assert last_sent(tmp_path) == "2026-11-29" and not due(SUNDAY, last_sent(tmp_path))


class FakeBot:
    def __init__(self):
        self.docs = []

    async def send_document(self, chat_id, document, caption=None, **kw):
        self.docs.append((chat_id, document.filename, caption))


@pytest.mark.asyncio
async def test_send_backup(tmp_path):
    bot = FakeBot()
    assert not await send_backup(bot, 42, tmp_path, SUNDAY)
    fill(tmp_path)
    assert await send_backup(bot, 42, tmp_path, SUNDAY)
    chat, name, caption = bot.docs[0]
    assert chat == 42 and name == "weather-bot-data-2026-11-29.zip" and "2 файлов" in caption


@pytest.mark.asyncio
async def test_loop_sends_once(tmp_path, monkeypatch):
    fill(tmp_path)
    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return SUNDAY

    monkeypatch.setattr(databackup, "datetime", Clock)
    bot, calls = FakeBot(), []

    async def stop(sec):
        calls.append(sec)
        if len(calls) >= 2:
            raise RuntimeError("stop")

    monkeypatch.setattr(databackup.asyncio, "sleep", stop)
    with pytest.raises(RuntimeError):
        await databackup.backup_loop(bot, tmp_path)
    assert len(bot.docs) == 1 and last_sent(tmp_path) == "2026-11-29"
