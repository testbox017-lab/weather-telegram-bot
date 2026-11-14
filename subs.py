"""Рассылка погоды по расписанию: каждые N часов или ежедневно в ЧЧ:ММ (по часовому поясу места)."""
# аннотации не вычисляются при определении класса: метод Subscriptions.list иначе
# перекрывает встроенный list в Python ≤ 3.13
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from weather import Place

INTERVALS = (1, 3, 6, 12, 24)   # допустимые интервалы, часов
MAX_TIMES = 3                    # не больше 3 времён в день
SUB_LIMIT = 5                    # не больше 5 рассылок на пользователя
_TIME_RE = re.compile(r"([01]?\d|2[0-3])[:.]([0-5]\d)")
_HOURS_RE = re.compile(r"^(?:каждые?\s*)?(\d{1,2})\s*(?:ч|час|часа|часов|h)?$")


def parse_schedule(text: str | None) -> dict | None:
    """«3», «3ч», «каждые 6 ч» → {"hours": 3}; «08:00», «7.30, 19:00» → {"times": [...]}; иначе None."""
    t = (text or "").strip().lower()
    if not t:
        return None
    m = _HOURS_RE.match(t)
    if m:
        h = int(m.group(1))
        return {"hours": h} if h in INTERVALS else None
    rest = re.sub(r"\bв\b", " ", t)
    times = [f"{int(h):02d}:{mi}" for h, mi in _TIME_RE.findall(rest)]
    leftover = _TIME_RE.sub("", rest).replace(",", " ").replace(";", " ").replace("и", " ").strip()
    if not times or leftover or len(times) > MAX_TIMES:
        return None
    return {"times": sorted(set(times))}


def split_place_schedule(args: str | None) -> tuple[str, dict | None]:
    """«Бахмач 3ч» → ("Бахмач", {"hours": 3}); «Бахмач» → ("Бахмач", None); «08:00» → ("", {...})."""
    tokens = (args or "").split()
    for k in range(min(len(tokens), MAX_TIMES * 2 + 1), 0, -1):
        sched = parse_schedule(" ".join(tokens[-k:]))
        if sched:
            return " ".join(tokens[:-k]), sched
    return " ".join(tokens), None


def next_run(sched: dict, now: datetime, tz: str = "UTC") -> datetime:
    """Следующее время отправки (aware, UTC). now — aware datetime."""
    now = now.astimezone(timezone.utc)
    if "hours" in sched:
        return now + timedelta(hours=int(sched["hours"]))
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    candidates = []
    for day in (local.date(), local.date() + timedelta(days=1)):
        for t in sched["times"]:
            h, mi = map(int, t.split(":"))
            # локальное «настенное» время → UTC через zoneinfo (корректно при переходе на летнее время)
            run = datetime(day.year, day.month, day.day, h, mi, tzinfo=zone).astimezone(timezone.utc)
            if run > now:
                candidates.append(run)
    return min(candidates)


def describe(sched: dict) -> str:
    if "times" in sched:
        return "ежедневно в " + ", ".join(sched["times"])
    h = int(sched["hours"])
    return {1: "каждый час", 24: "раз в сутки"}.get(h, f"каждые {h} ч")


def local_time(dt: datetime, tz: str) -> str:
    loc = dt.astimezone(ZoneInfo(tz))
    return f"{loc:%d.%m %H:%M}"


class Subscriptions:
    """user_id → список {id, name, lat, lon, sched, tz, next}; хранится в JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): [s for s in v if isinstance(s, dict) and {"id", "sched", "next"} <= s.keys()]
                          for k, v in raw.items() if isinstance(v, list)}
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    def list(self, user_id: int) -> list[dict]:
        return list(self._data.get(str(user_id), []))

    def add(self, user_id: int, place: Place, sched: dict, tz: str, now: datetime) -> dict | None:
        """Новая рассылка; None, если уже SUB_LIMIT. Та же точка + то же расписание — заменяется."""
        items = self._data.setdefault(str(user_id), [])
        items[:] = [s for s in items if not (s["sched"] == sched and round(s["lat"], 3) == round(place.lat, 3)
                                            and round(s["lon"], 3) == round(place.lon, 3))]
        if len(items) >= SUB_LIMIT:
            return None
        sub = {"id": max((s["id"] for s in items), default=0) + 1, "name": place.name,
               "lat": place.lat, "lon": place.lon, "sched": sched, "tz": tz,
               "next": next_run(sched, now, tz).isoformat()}
        items.append(sub)
        self._save()
        return sub

    def remove(self, user_id: int, sub_id: int) -> dict | None:
        items = self._data.get(str(user_id), [])
        for i, s in enumerate(items):
            if s["id"] == sub_id:
                items.pop(i)
                self._save()
                return s
        return None

    def remove_index(self, user_id: int, number: int) -> dict | None:
        items = self.list(user_id)
        return self.remove(user_id, items[number - 1]["id"]) if 1 <= number <= len(items) else None

    def remove_all(self, user_id: int) -> int:
        n = len(self._data.pop(str(user_id), []))
        if n:
            self._save()
        return n

    def due(self, now: datetime) -> list[tuple[int, dict]]:
        return [(int(uid), s) for uid, items in self._data.items() for s in items
                if datetime.fromisoformat(s["next"]) <= now]

    def advance(self, user_id: int, sub_id: int, now: datetime) -> None:
        """Следующая отправка от текущего момента: пропущенное за время простоя досылается один раз."""
        for s in self._data.get(str(user_id), []):
            if s["id"] == sub_id:
                s["next"] = next_run(s["sched"], now, s.get("tz", "UTC")).isoformat()
                self._save()

    @staticmethod
    def place(sub: dict) -> Place:
        return Place(sub["name"], float(sub["lat"]), float(sub["lon"]))


async def run_due(subs: Subscriptions, now: datetime, send, blocked_exc: tuple = (), pause: float = 0.3) -> int:
    """Отправить все наступившие рассылки. send(user_id, sub) — корутина.

    Пользователь заблокировал бота (blocked_exc) → удаляем все его рассылки;
    другие ошибки — в лог, попробуем в следующий раз по расписанию.
    """
    sent = 0
    for uid, sub in subs.due(now):
        try:
            await send(uid, sub)
            sent += 1
        except blocked_exc:
            logging.info("пользователь %s заблокировал бота — удаляю рассылки", uid)
            subs.remove_all(uid)
            continue
        except Exception:
            logging.exception("ошибка рассылки для %s", uid)
        subs.advance(uid, sub["id"], now)
        if pause:
            await asyncio.sleep(pause)
    return sent
