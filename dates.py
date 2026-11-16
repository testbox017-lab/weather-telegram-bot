"""Выбор даты: разбор ввода, выбор источника данных, callback-данные календаря."""
import re
from datetime import date, timedelta

from i18n import N_

MIN_DATE = date(1940, 1, 1)
FORECAST_AHEAD = 15   # прогноз: сегодня + 15 дней (всего 16)
FORECAST_BACK = 7     # прошлые дни до недели назад берём из прогнозного API, раньше — из архива
TOO_FAR = N_("Прогноз доступен максимум на 16 дней вперёд")  # тексты ошибок переводятся при показе: _(...)
TOO_OLD = N_("Архив погоды начинается с 01.01.1940")

RELATIVE = {"сегодня": 0, "завтра": 1, "послезавтра": 2, "вчера": -1, "позавчера": -2,
            "сьогодні": 0, "післязавтра": 2, "вчора": -1, "учора": -1, "позавчора": -2,  # по-украински
            "today": 0, "tomorrow": 1, "yesterday": -1}
_DATE_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2}|\d{4}))?$")


def parse_date(text: str | None, today: date) -> date | None:
    """«21.11», «21.11.2026», «21.11.26», «завтра» → date; None, если не дата."""
    t = (text or "").strip().lower()
    if t in RELATIVE:
        return today + timedelta(days=RELATIVE[t])
    m = _DATE_RE.match(t)
    if not m:
        return None
    d, mo, y = m.groups()
    year = today.year if y is None else int(y) + (2000 if len(y) == 2 else 0)
    try:
        return date(year, int(mo), int(d))
    except ValueError:
        return None


def split_date_args(args: str | None, today: date) -> tuple[date | None, str]:
    """«/date завтра Казань» → (дата, "Казань"); дата всегда первым словом."""
    parts = (args or "").strip().split(maxsplit=1)
    if not parts:
        return None, ""
    return parse_date(parts[0], today), (parts[1] if len(parts) > 1 else "")


def date_source(day: date, today: date) -> str:
    """'forecast' | 'archive' | 'future' (слишком далеко) | 'old' (раньше 1940)."""
    if day > today + timedelta(days=FORECAST_AHEAD):
        return "future"
    if day < MIN_DATE:
        return "old"
    if day < today - timedelta(days=FORECAST_BACK):
        return "archive"
    return "forecast"


def source_error(src: str) -> str | None:
    return {"future": TOO_FAR, "old": TOO_OLD}.get(src)


def build_date_cb(day: date, lat: float, lon: float) -> str:
    return f"d:{day:%Y%m%d}:{lat:.3f}:{lon:.3f}"


def parse_date_cb(data: str | None) -> tuple[date, float, float] | None:
    try:
        prefix, d, lat, lon = (data or "").split(":")
        if prefix != "d" or len(d) != 8:
            return None
        day = date(int(d[:4]), int(d[4:6]), int(d[6:]))
        lat, lon = float(lat), float(lon)
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return day, lat, lon


def build_cal_cb(page: str, lat: float, lon: float) -> str:
    """page: 'f' — ближайшие 16 дней, 'p' — прошлые 14 дней, 'i' — ввести дату."""
    return f"c:{page}:{lat:.3f}:{lon:.3f}"


def parse_cal_cb(data: str | None) -> tuple[str, float, float] | None:
    try:
        prefix, page, lat, lon = (data or "").split(":")
        lat, lon = float(lat), float(lon)
    except ValueError:
        return None
    if prefix != "c" or page not in ("f", "p", "i") or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return page, lat, lon


def calendar_days(page: str, today: date) -> list[date]:
    if page == "p":
        return [today - timedelta(days=k) for k in range(14, 0, -1)]
    return [today + timedelta(days=k) for k in range(FORECAST_AHEAD + 1)]
