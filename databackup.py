"""Бэкап данных в Telegram: раз в неделю бот присылает владельцу zip с JSON-файлами из DATA_DIR.

Копии на сервере (weather-bot-backup) лежат на том же VPS; эта — вне его, на случай, если сервер пропадёт.
Кому — ADMIN_CHAT_ID из .env, иначе единственный пользователь бота (как у сторожа). /backup — прислать сейчас.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from i18n import _

WEEKDAY, FROM_UTC = 6, 9          # воскресенье с 09:00 UTC (11:00 по Киеву зимой)
STATE_FILE = "backup_sent.json"   # когда последний раз отправляли
SKIP = {"heartbeat.json", "fsm.json", STATE_FILE}
USER_FILES = ("saved_places.json", "last_places.json", "subscriptions.json", "alerts.json", "prefs.json")
CHECK_EVERY = 1800


def owner(data_dir: Path, env: dict | None = None) -> int | None:
    """ADMIN_CHAT_ID, а если его нет — единственный пользователь из файлов данных."""
    env = os.environ if env is None else env
    admin = (env.get("ADMIN_CHAT_ID") or "").strip()
    if admin.lstrip("-").isdigit():
        return int(admin)
    ids: set[str] = set()
    for name in USER_FILES:
        try:
            ids |= {k for k in json.loads((data_dir / name).read_text(encoding="utf-8")) if k.lstrip("-").isdigit()}
        except Exception:
            pass
    return int(ids.pop()) if len(ids) == 1 else None


def make_zip(data_dir: Path) -> tuple[bytes, int]:
    """zip со всеми *.json из data_dir (кроме служебных). Возвращает (байты, сколько файлов)."""
    buf, n = io.BytesIO(), 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(data_dir.glob("*.json")):
            if f.name in SKIP or not f.is_file():
                continue
            z.write(f, f.name)
            n += 1
    return buf.getvalue(), n


def last_sent(data_dir: Path) -> str | None:
    try:
        return json.loads((data_dir / STATE_FILE).read_text(encoding="utf-8")).get("sent")
    except Exception:
        return None


def mark_sent(data_dir: Path, day: str) -> None:
    try:
        (data_dir / STATE_FILE).write_text(json.dumps({"sent": day}), encoding="utf-8")
    except OSError:
        logging.exception("backup: не удалось записать %s", STATE_FILE)


def due(now: datetime, sent: str | None) -> bool:
    return now.weekday() == WEEKDAY and now.hour >= FROM_UTC and sent != now.date().isoformat()


async def send_backup(bot, chat_id: int, data_dir: Path, now: datetime) -> bool:
    """Отправить архив в чат. False — нечего отправлять."""
    from aiogram.types import BufferedInputFile

    blob, n = make_zip(data_dir)
    if not n:
        return False
    caption = _("💾 Бэкап данных бота за {d:%d.%m.%Y}: {n} файлов. Чтобы восстановить, распакуйте архив "
                "в папку данных (на сервере /opt/weather-bot/data) и перезапустите бота.", d=now, n=n)
    await bot.send_document(chat_id, BufferedInputFile(blob, f"weather-bot-data-{now:%Y-%m-%d}.zip"),
                            caption=caption, disable_notification=True)
    return True


async def backup_loop(bot, data_dir: Path, every: float = CHECK_EVERY):
    """Раз в неделю прислать бэкап владельцу. Ошибка — попробуем при следующей проверке."""
    while True:
        now = datetime.now(timezone.utc)
        try:
            if due(now, last_sent(data_dir)):
                chat = owner(data_dir)
                if chat is None:
                    logging.warning("backup: не знаю, кому отправить (нет ADMIN_CHAT_ID, пользователей не один)")
                    mark_sent(data_dir, now.date().isoformat())
                else:
                    from prefs import current_user

                    token = current_user.set(chat)  # подпись — на языке владельца
                    try:
                        if await send_backup(bot, chat, data_dir, now):
                            logging.info("backup: архив отправлен в Telegram")
                    finally:
                        current_user.reset(token)
                    mark_sent(data_dir, now.date().isoformat())
        except Exception:
            logging.exception("backup: не удалось отправить архив")
        await asyncio.sleep(every)
