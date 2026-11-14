"""Солнце (из Open-Meteo) и луна (расчёт через astral): восход, заход, фаза."""
import math
from datetime import date, datetime, timedelta, timezone

from astral import Observer
from astral.moon import moonrise, moonset, phase
from astral.sun import dawn, dusk, noon

SYNODIC = 29.530588853  # синодический месяц, сут.

# (возраст луны до, эмодзи, название)
PHASES = [
    (1.0, "🌑", "Новолуние"),
    (6.4, "🌒", "Растущий серп"),
    (8.4, "🌓", "Первая четверть"),
    (13.8, "🌔", "Растущая луна"),
    (15.8, "🌕", "Полнолуние"),
    (21.1, "🌖", "Убывающая луна"),
    (23.1, "🌗", "Последняя четверть"),
    (28.5, "🌘", "Убывающий серп"),
    (99.0, "🌑", "Новолуние"),
]


def moon_age(day: date) -> float:
    """Возраст луны в сутках (0 = новолуние, ~14.8 = полнолуние)."""
    return phase(day) * SYNODIC / 28


def moon_phase(day: date) -> tuple[str, str, int]:
    """(эмодзи, название, освещённость %)."""
    age = moon_age(day)
    emoji, name = next((e, n) for limit, e, n in PHASES if age < limit)
    lit = round((1 - math.cos(2 * math.pi * age / SYNODIC)) / 2 * 100)
    return emoji, name, lit


def next_phases(day: date, horizon: int = 32) -> list[tuple[str, str, date]]:
    """Ближайшие новолуние и полнолуние: [(эмодзи, название, дата)] по порядку."""
    found = {}
    prev = moon_age(day)
    for k in range(1, horizon):
        d = day + timedelta(days=k)
        age = moon_age(d)
        before = d - timedelta(days=1)
        # момент фазы лежит между before и d — берём ближайший к нему день
        if age < prev and "new" not in found:  # возраст «обнулился»
            found["new"] = ("🌑", "Новолуние", d if age < SYNODIC - prev else before)
        if prev < SYNODIC / 2 <= age and "full" not in found:
            half = SYNODIC / 2
            found["full"] = ("🌕", "Полнолуние", d if age - half < half - prev else before)
        prev = age
    return sorted(found.values(), key=lambda x: x[2])


def _hm(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "—"


def _moon_event(func, observer: Observer, day: date, tz) -> datetime | None:
    try:
        return func(observer, day, tzinfo=tz)
    except ValueError:  # в этот день луна не восходит / не заходит
        return None


def twilight_line(obs: Observer, day: date, tz) -> str | None:
    """«🌄 Светает с 06:20 · ☀️ Полдень 11:41 · 🌆 Темнеет к 17:05» — гражданские сумерки (солнце на 6° под
    горизонтом): светло уже без фонарей. Полярной ночью или белыми ночами сумерек нет — строку пропускаем."""
    try:
        start, mid, end = dawn(obs, day, tzinfo=tz), noon(obs, day, tzinfo=tz), dusk(obs, day, tzinfo=tz)
    except ValueError:
        return None
    return f"🌄 Светает с {start:%H:%M} · ☀️ Полдень {mid:%H:%M} · 🌆 Темнеет к {end:%H:%M}"


def astro_text(lat: float, lon: float, data: dict, next_phases_line: bool = True) -> str:
    """Блок про солнце и луну на день из data["daily"]["time"][0] (по местному времени точки)."""
    tz = timezone(timedelta(seconds=data.get("utc_offset_seconds", 0)))
    d = data.get("daily", {})
    today = date.fromisoformat(d["time"][0]) if d.get("time") else datetime.now(tz).date()
    lines = []

    if d.get("sunrise") and d.get("sunset"):
        rise = datetime.fromisoformat(d["sunrise"][0])
        sset = datetime.fromisoformat(d["sunset"][0])
        line = f"🌅 Восход {rise:%H:%M} · 🌇 Заход {sset:%H:%M}"
        if d.get("daylight_duration"):
            mins = round(d["daylight_duration"][0] / 60)
            line += f" (день {mins // 60} ч {mins % 60:02d} мин)"
        lines.append(line)

    obs = Observer(latitude=lat, longitude=lon)
    twilight = twilight_line(obs, today, tz)
    if twilight:
        lines.append(twilight)
    mrise = _moon_event(moonrise, obs, today, tz)
    mset = _moon_event(moonset, obs, today, tz)
    emoji, name, lit = moon_phase(today)
    lines.append(f"🌙 Луна: восход {_hm(mrise)} · заход {_hm(mset)}")
    lines.append(f"{emoji} {name}, освещена на {lit}%")
    nxt = next_phases(today) if next_phases_line else []
    if nxt:
        lines.append(" · ".join(f"{e} {n} {d:%d.%m}" for e, n, d in nxt))
    return "\n".join(lines)
