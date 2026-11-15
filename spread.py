"""Сравнение моделей прогноза (ECMWF, ICON, GFS): насколько они расходятся по дням.

Чем больше разброс между моделями, тем меньше уверенности в прогнозе на этот день.
"""
from __future__ import annotations

from datetime import date

from prefs import MODELS
from weather import DAYS_RU

SPREAD_MODELS = ["ecmwf_ifs025", "icon_seamless", "gfs_seamless"]
CALM, SOME = 2, 4  # разброс температуры, °C: до 2° модели согласны, до 4° — расходятся немного
WET = 1.0  # мм за сутки: «будет дождь»
DRY = 0.2  # мм за сутки: «сухо»


def series(block: dict | None, key: str, model: str) -> list:
    return (block or {}).get(f"{key}_{model}") or []


def label(model: str) -> str:
    return MODELS.get(model, (model,))[0]


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else str(t)


def _at(col: list, i: int):
    return col[i] if i < len(col) else None


def day_spread(daily: dict, i: int, models: list[str]) -> dict | None:
    """Разброс моделей за день i: диапазоны макс./мин. температуры и осадков, сколько моделей есть."""
    highs = [v for m in models if (v := _at(series(daily, "temperature_2m_max", m), i)) is not None]
    lows = [v for m in models if (v := _at(series(daily, "temperature_2m_min", m), i)) is not None]
    precs = [v for m in models if (v := _at(series(daily, "precipitation_sum", m), i)) is not None]
    if not highs or not lows:
        return None
    spread = max(max(highs) - min(highs), max(lows) - min(lows))
    return {"hi": (min(highs), max(highs)), "lo": (min(lows), max(lows)), "prec": (min(precs), max(precs))
            if precs else None, "spread": spread, "n": len(highs),
            "rain_doubt": bool(precs) and max(precs) >= WET and min(precs) < DRY}


def mark(s: dict) -> str:
    if s["spread"] > SOME:
        return "⚠️"
    if s["spread"] > CALM or s["rain_doubt"]:
        return "🟡"
    return "✅"


def format_spread(name: str, data: dict, models: list[str] = SPREAD_MODELS) -> str:
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    lines = [f"🧪 <b>{name}</b> — что говорят разные модели", ""]
    first_doubt = None
    for i, t in enumerate(times):
        s = day_spread(daily, i, models)
        if not s:
            continue
        d = date.fromisoformat(t)
        hi = _deg(s["hi"][0]) if round(s["hi"][0]) == round(s["hi"][1]) else f"{_deg(s['hi'][0])}…{_deg(s['hi'][1])}"
        lo = _deg(s["lo"][0]) if round(s["lo"][0]) == round(s["lo"][1]) else f"{_deg(s['lo'][0])}…{_deg(s['lo'][1])}"
        rain = ""
        if s["prec"] and s["prec"][1] >= DRY:
            p0, p1 = s["prec"]
            rain = f", 💧 {p1:.1f} мм" if p1 - p0 < 0.5 else f", 💧 {p0:.1f}–{p1:.1f} мм"
        note = " (не все модели)" if s["n"] < len(models) else ""
        lines.append(f"{mark(s)} {DAYS_RU[d.weekday()]} {d:%d.%m}: днём {hi}°, ночью {lo}°{rain}{note}")
        if first_doubt is None and mark(s) != "✅":
            first_doubt = d
    if len(lines) == 2:
        return f"🧪 <b>{name}</b>\nМодели не прислали данных 🤷"
    lines.append("")
    if first_doubt is None:
        lines.append("Модели согласны на всю неделю — прогнозу можно доверять 👍")
    elif first_doubt == date.fromisoformat(times[0]):
        lines.append("Модели расходятся уже сегодня — погода может сильно отличаться от прогноза.")
    else:
        lines.append(f"Модели согласны до {DAYS_RU[first_doubt.weekday()].lower()} {first_doubt:%d.%m}, "
                     "дальше прогноз менее надёжен.")
    lines.append("✅ разница до 2° · 🟡 до 4° или спорный дождь · ⚠️ больше 4°")
    lines.append("Модели: " + ", ".join(label(m) for m in models))
    return "\n".join(lines)
