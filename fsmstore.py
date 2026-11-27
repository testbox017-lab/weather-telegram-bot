"""Ожидание ввода (FSM aiogram), которое переживает перезапуск бота: состояние и данные в JSON-файле.

Это MemoryStorage, который после каждого изменения пишет непустые записи в файл, а при старте читает их.
Записи старше MAX_AGE при чтении отбрасываются: вопрос, заданный вчера, уже неактуален.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

MAX_AGE = 24 * 3600
FIELDS = ("bot_id", "chat_id", "user_id", "thread_id", "business_connection_id", "destiny")


class JsonFileStorage(MemoryStorage):
    def __init__(self, path: Path, now: float | None = None):
        super().__init__()
        self.path = Path(path)
        self._stamp: dict[StorageKey, float] = {}
        now = time.time() if now is None else now
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw if isinstance(raw, list) else []:
                if now - float(item.get("ts") or 0) > MAX_AGE:
                    continue
                key = StorageKey(**{f: item["key"].get(f) for f in FIELDS if f in item["key"]})
                rec = self.storage[key]
                rec.state, rec.data = item.get("state"), dict(item.get("data") or {})
                self._stamp[key] = float(item["ts"])
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def _save(self, key: StorageKey) -> None:
        self._stamp[key] = time.time()
        items = []
        for k, rec in list(self.storage.items()):
            if rec.state is None and not rec.data:
                continue
            items.append({"key": {f: getattr(k, f) for f in FIELDS}, "state": rec.state, "data": rec.data,
                          "ts": self._stamp.get(k, time.time())})
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except (OSError, TypeError, ValueError):
            logging.exception("не удалось сохранить %s", self.path)

    async def set_state(self, key: StorageKey, state: str | State | None = None) -> None:
        await super().set_state(key, state)
        self._save(key)

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await super().set_data(key, data)
        self._save(key)
