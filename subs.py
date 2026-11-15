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
QUIET_FROM, QUIET_TO = 23, 7     # рассылки «каждые N ч» ночью не приходят (по местному времени места)
_TIME_RE = re.compile(r"([01]?\d|2[0-3])[:.]([0-5]\d)")
_HOURS_RE = re.compile(r"^(?:каждые?\s*)?(\d{1,2})\s*(?:ч|час|часа|часов|h)?$")


DAY_NAMES = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
_DAY_WORDS = {
    "будни": [0, 1, 2, 3, 4], "будням": [0, 1, 2, 3, 4], "будние": [0, 1, 2, 3, 4],
    "выходные": [5, 6], "выходным": [5, 6],
    "понедельник": [0], "понедельникам": [0], "вторник": [1], "вторникам": [1],
    "среда": [2], "среду": [2], "средам": [2], "четверг": [3], "четвергам": [3],
    "пятница": [4], "пятницу": [4], "пятницам": [4], "суббота": [5], "субботу": [5], "субботам": [5],
    "воскресенье": [6], "воскресеньям": [6],
    **{d: [i] for i, d in enumerate(DAY_NAMES)},
}
_FILLER = {"по", "в", "во", "и", "дни", "день"}


def _take_days(t: str) -> tuple[str, list[int] | None]:
    """Вынуть из текста дни недели: «по будням 07:30» → ("07:30", [0..4])."""
    days, rest, found = set(), [], False
    for tok in re.split(r"[\s,;]+", t):
        if tok in _DAY_WORDS:
            days.update(_DAY_WORDS[tok])
            found = True
        elif tok not in _FILLER or not found:
            rest.append(tok)
    if not found:
        return t, None
    rest = [x for x in rest if x not in _FILLER]
    return " ".join(rest), sorted(days)


def parse_schedule(text: str | None) -> dict | None:
    """«3», «3ч», «каждые 6 ч» → {"hours": 3}; «08:00», «7.30, 19:00» → {"times": [...]}; иначе None.

    Ежедневное время можно ограничить днями недели: «по будням 07:30», «сб вс 10:00» → {"times", "days"}.
    """
    t = (text or "").strip().lower()
    if not t:
        return None
    t, days = _take_days(t)
    if days is not None:
        sched = parse_schedule(t)
        if not sched or "times" not in sched or len(days) == 7:
            return sched if sched and len(days) == 7 and "times" in sched else None
        return {**sched, "days": days}
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


SHORT_WORDS = {"кратко", "коротко", "кратко.", "short"}


def split_short(args: str | None) -> tuple[str, bool]:
    """«Бахмач 3ч кратко» → ("Бахмач 3ч", True): слово «кратко» в любом месте включает краткий формат."""
    tokens = (args or "").split()
    rest = [t for t in tokens if t.lower() not in SHORT_WORDS]
    return " ".join(rest), len(rest) != len(tokens)


_COND_RE = re.compile(r"(?:^|\s)если\s+(.+)$")
_NUM_RE = re.compile(r"([-−+]?\d{1,2})")


def parse_condition(text: str) -> str | None:
    """«дождь» → "precip", «снег» → "snow", «мороз» → "frost", «ниже -5» → "below:-5", «выше 25» → "above:25"."""
    t = text.strip().lower().replace("°", " ").replace("c", " ").replace("с ", " ")
    m = _NUM_RE.search(t)
    num = int(m.group(1).replace("−", "-")) if m else None
    if num is not None and any(w in t for w in ("ниже", "холоднее", "меньше", "<")):
        return f"below:{num}"
    if num is not None and any(w in t for w in ("выше", "теплее", "больше", ">", "жара")):
        return f"above:{num}"
    if "снег" in t:
        return "snow"
    if any(w in t for w in ("дожд", "осадк", "ливен", "гроз")):
        return "precip"
    if any(w in t for w in ("мороз", "заморо", "минус")):
        return "frost"
    return None


def split_condition(args: str | None) -> tuple[str, str | None, bool]:
    """«Бахмач 07:00 если дождь» → ("Бахмач 07:00", "precip", True). Третье — было ли слово «если»."""
    a = args or ""
    m = _COND_RE.search(a.lower())
    if not m:
        return a.strip(), None, False
    return a[:m.start()].strip(), parse_condition(m.group(1)), True


def describe_cond(cond: str | None) -> str:
    if not cond:
        return ""
    kind, _, value = cond.partition(":")
    if kind in ("below", "above"):
        n = int(value)
        sign = "+" if n > 0 else ""
        return f"если {'ниже' if kind == 'below' else 'выше'} {sign}{n}°"
    return {"precip": "если будут осадки", "snow": "если будет снег", "frost": "если будет мороз"}.get(kind, "")


def condition_met(cond: str | None, data: dict) -> bool:
    """Выполнено ли условие рассылки по прогнозу на ближайшие 12 часов (мороз — 24 часа)."""
    if not cond:
        return True
    from advice import is_wet, upcoming

    kind, _, value = cond.partition(":")
    hours = upcoming(data, 24 if kind == "frost" else 12)
    temps = [h["temp"] for h in hours if h["temp"] is not None]
    if kind == "precip":
        rain = ((data.get("daily") or {}).get("precipitation_sum") or [0])[0] or 0
        return any(is_wet(h) for h in hours) or rain >= 0.5
    if kind == "snow":
        return any(is_wet(h) and h["code"] in {71, 73, 75, 77, 85, 86} for h in hours)
    if kind == "frost":
        return bool(temps) and min(temps) <= 0
    if kind == "below":
        return bool(temps) and min(temps) <= int(value)
    if kind == "above":
        return bool(temps) and max(temps) >= int(value)
    return True


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
    zone = ZoneInfo(tz)
    if "hours" in sched:
        run = (now + timedelta(hours=int(sched["hours"]))).astimezone(zone)
        if is_quiet(run):  # ночью не будим: переносим на утро
            day = run.date() if run.hour < QUIET_TO else run.date() + timedelta(days=1)
            run = datetime(day.year, day.month, day.day, QUIET_TO, 0, tzinfo=zone)
        return run.astimezone(timezone.utc)
    local = now.astimezone(zone)
    candidates = []
    days = set(sched.get("days") or range(7))
    for day in (local.date() + timedelta(days=k) for k in range(8)):
        if day.weekday() not in days:
            continue
        for t in sched["times"]:
            h, mi = map(int, t.split(":"))
            # локальное «настенное» время → UTC через zoneinfo (корректно при переходе на летнее время)
            run = datetime(day.year, day.month, day.day, h, mi, tzinfo=zone).astimezone(timezone.utc)
            if run > now:
                candidates.append(run)
    return min(candidates)


def is_quiet(local: datetime) -> bool:
    return local.hour >= QUIET_FROM or local.hour < QUIET_TO


def quiet_now(sub: dict, now: datetime) -> bool:
    """Рассылка «каждые N ч», а у места сейчас ночь (старые записи могли запланировать отправку на ночь)."""
    return "hours" in sub["sched"] and is_quiet(now.astimezone(ZoneInfo(sub.get("tz", "UTC"))))


def describe_days(days: list[int] | None) -> str:
    if not days or len(days) == 7:
        return "ежедневно"
    if days == [0, 1, 2, 3, 4]:
        return "по будням"
    if days == [5, 6]:
        return "по выходным"
    return "по " + ", ".join(DAY_NAMES[d] for d in days)


def describe(sched: dict) -> str:
    if "times" in sched:
        return describe_days(sched.get("days")) + " в " + ", ".join(sched["times"])
    h = int(sched["hours"])
    return {1: "каждый час", 24: "раз в сутки"}.get(h, f"каждые {h} ч")


def local_time(dt: datetime, tz: str) -> str:
    loc = dt.astimezone(ZoneInfo(tz))
    return f"{loc:%d.%m %H:%M}"


class Subscriptions:
    """user_id → список {id, name, lat, lon, sched, tz, next, short}; хранится в JSON-файле.

    short=True — краткий формат (три строки без графиков); у старых записей поля нет, это «полный».
    """

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

    def add(self, user_id: int, place: Place, sched: dict, tz: str, now: datetime,
            short: bool = False, cond: str | None = None) -> dict | None:
        """Новая рассылка; None, если уже SUB_LIMIT. Та же точка + то же расписание — заменяется."""
        items = self._data.setdefault(str(user_id), [])
        items[:] = [s for s in items if not (s["sched"] == sched and s.get("cond") == cond
                                            and round(s["lat"], 3) == round(place.lat, 3)
                                            and round(s["lon"], 3) == round(place.lon, 3))]
        if len(items) >= SUB_LIMIT:
            return None
        sub = {"id": max((s["id"] for s in items), default=0) + 1, "name": place.name,
               "lat": place.lat, "lon": place.lon, "sched": sched, "tz": tz,
               "next": next_run(sched, now, tz).isoformat(), "short": short}
        if cond:
            sub["cond"] = cond
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

    def toggle_short(self, user_id: int, sub_id: int) -> dict | None:
        """Переключить формат рассылки полный ↔ краткий; возвращает рассылку или None."""
        for s in self._data.get(str(user_id), []):
            if s["id"] == sub_id:
                s["short"] = not s.get("short", False)
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

    def advance(self, user_id: int, sub_id: int, now: datetime, morning: bool = False) -> None:
        """Следующая отправка от текущего момента: пропущенное за время простоя досылается один раз.
        morning=True — ночью рассылку пропустили, следующая утром в QUIET_TO."""
        for s in self._data.get(str(user_id), []):
            if s["id"] == sub_id:
                sched = {"hours": 0} if morning else s["sched"]
                s["next"] = next_run(sched, now, s.get("tz", "UTC")).isoformat()
                self._save()

    def retry_at(self, user_id: int, sub_id: int, when: datetime) -> None:
        """Повторить рассылку в when (после сбоя сети), не трогая расписание."""
        for s in self._data.get(str(user_id), []):
            if s["id"] == sub_id:
                s["next"] = when.isoformat()
                self._save()

    @staticmethod
    def place(sub: dict) -> Place:
        return Place(sub["name"], float(sub["lat"]), float(sub["lon"]))


RETRY_EVERY = timedelta(minutes=5)  # сбой сети: повторить через 5 минут
RETRY_TIMES = 2                     # не больше двух повторов, дальше — по расписанию
_retries: dict[tuple[int, int], int] = {}


async def run_due(subs: Subscriptions, now: datetime, send, blocked_exc: tuple = (), pause: float = 0.3,
                  retry_exc: tuple = ()) -> int:
    """Отправить все наступившие рассылки. send(user_id, sub) — корутина.

    Пользователь заблокировал бота (blocked_exc) → удаляем все его рассылки;
    сбой сети (retry_exc, например таймаут Telegram) → короткая строка в лог и повтор через RETRY_EVERY,
    не больше RETRY_TIMES раз; другие ошибки — в лог с трейсбеком, попробуем в следующий раз по расписанию.
    """
    sent = 0
    for uid, sub in subs.due(now):
        if quiet_now(sub, now):  # ночь — не отправляем, переносим на утро
            subs.advance(uid, sub["id"], now, morning=True)
            continue
        rkey = (uid, sub["id"])
        try:
            await send(uid, sub)
            sent += 1
        except blocked_exc:
            logging.info("пользователь %s заблокировал бота — удаляю рассылки", uid)
            subs.remove_all(uid)
            _retries.pop(rkey, None)
            continue
        except retry_exc as e:
            tries = _retries.get(rkey, 0)
            if tries < RETRY_TIMES:
                _retries[rkey] = tries + 1
                logging.warning("рассылка для %s не ушла (%s), повтор через %d мин",
                                uid, e, RETRY_EVERY.seconds // 60)
                subs.retry_at(uid, sub["id"], now + RETRY_EVERY)
                continue
            logging.warning("рассылка для %s не ушла и после %d повторов (%s), следующая — по расписанию",
                            uid, tries, e)
        except Exception:
            logging.exception("ошибка рассылки для %s", uid)
        _retries.pop(rkey, None)
        subs.advance(uid, sub["id"], now)
        if pause:
            await asyncio.sleep(pause)
    return sent
