"""Режим «Среднее»: прогноз как среднее ECMWF, ICON, GFS и OpenWeatherMap (если задан ключ).

Числа (температура, осадки, ветер, влажность, давление) — среднее тех источников, что прислали значение.
Код погоды, направление ветра, восход, УФ и остальное — от «Авто» Open-Meteo: среднее «ясно» и «дождь»
не имеет смысла. Под прогнозом бот пишет, из скольких источников среднее и насколько они расходятся сегодня.
"""
from __future__ import annotations

MEMBERS = ["ecmwf_ifs025", "icon_seamless", "gfs_seamless"]
KEY = "mean"  # значение настройки prefs "model"
OWM = "owm"

CURRENT = ["temperature_2m", "apparent_temperature", "relative_humidity_2m", "wind_speed_10m", "wind_gusts_10m",
           "pressure_msl", "cloud_cover", "dew_point_2m", "precipitation"]
HOURLY = ["temperature_2m", "precipitation", "precipitation_probability", "wind_speed_10m", "wind_gusts_10m",
          "relative_humidity_2m", "dew_point_2m"]
DAILY = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max",
         "wind_speed_10m_max", "wind_gusts_10m_max", "relative_humidity_2m_mean", "relative_humidity_2m_min",
         "relative_humidity_2m_max"]
WHOLE = {"relative_humidity_2m", "cloud_cover", "precipitation_probability", "precipitation_probability_max",
         "relative_humidity_2m_mean", "relative_humidity_2m_min", "relative_humidity_2m_max"}


def _mean(vals: list, key: str):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    return round(m) if key in WHOLE else round(m, 2)


def _average_block(block: dict, members: dict, keys: list[str], extra: list[dict] = ()) -> None:
    """block[key][i] := среднее members[f"{key}_{m}"][i] и extra (OWM: время → значения)."""
    times = block.get("time") or []
    for key in keys:
        col = block.get(key)
        if not isinstance(col, list):
            continue
        cols = [members.get(f"{key}_{m}") or [] for m in MEMBERS]
        for i in range(len(col)):
            vals = [c[i] for c in cols if i < len(c)]
            if i < len(times):
                vals += [(e.get(times[i]) or {}).get(key) for e in extra]
            v = _mean(vals, key)
            if v is not None:
                col[i] = v


def owm_daily(recon: dict, days: list[str], min_hours: int) -> dict[str, dict]:
    """Суточные значения OWM для почти полных дней: "2026-11-17" → {"temperature_2m_max": ...}."""
    out = {}
    for day in days:
        rows = [r for t, r in recon.items() if t.startswith(day)]
        if len(rows) < min_hours:
            continue
        temps = [r["temperature_2m"] for r in rows if r.get("temperature_2m") is not None]
        winds = [r["wind_speed_10m"] for r in rows if r.get("wind_speed_10m") is not None]
        gusts = [r["wind_gusts_10m"] for r in rows if r.get("wind_gusts_10m") is not None]
        hums = [r["relative_humidity_2m"] for r in rows if r.get("relative_humidity_2m") is not None]
        out[day] = {"temperature_2m_max": max(temps, default=None), "temperature_2m_min": min(temps, default=None),
                    "precipitation_sum": round(sum(r.get("precipitation") or 0 for r in rows), 1),
                    "precipitation_probability_max": max((r.get("precipitation_probability") or 0 for r in rows)),
                    "wind_speed_10m_max": max(winds, default=None), "wind_gusts_10m_max": max(gusts, default=None),
                    "relative_humidity_2m_mean": sum(hums) / len(hums) if hums else None,
                    "relative_humidity_2m_min": min(hums, default=None),
                    "relative_humidity_2m_max": max(hums, default=None)}
    return out


def today_spread(multi: dict, owm_today: dict | None) -> float | None:
    """Насколько источники расходятся сегодня: наибольшая разница дневных максимумов или минимумов, °C."""
    daily = multi.get("daily") or {}
    worst = None
    for key in ("temperature_2m_max", "temperature_2m_min"):
        vals = [(daily.get(f"{key}_{m}") or [None])[0] for m in MEMBERS]
        if owm_today:
            vals.append(owm_today.get(key))
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            d = max(vals) - min(vals)
            worst = d if worst is None else max(worst, d)
    return worst


def apply(data: dict, multi: dict, owm_current: dict | None = None, owm_forecast: dict | None = None) -> dict:
    """data — ответ «Авто» после split_yesterday, multi — тот же запрос с models=MEMBERS (тоже после
    split_yesterday), owm_* — ответы OpenWeatherMap или None. Меняет и возвращает data."""
    import owm

    recon, cur_owm, owm_days = {}, {}, {}
    if owm_forecast is not None:
        recon = owm.hourly(owm_forecast, int(data.get("utc_offset_seconds") or 0))
        cur_owm = owm.parse_current(owm_current or {})
        owm_days = owm_daily(recon, (data.get("daily") or {}).get("time") or [], owm.MODELS_HOURS)
    cur, mcur = data.get("current") or {}, multi.get("current") or {}
    for key in CURRENT:
        if key in cur:
            v = _mean([mcur.get(f"{key}_{m}") for m in MEMBERS] + [cur_owm.get(key)], key)
            if v is not None:
                cur[key] = v
    _average_block(data.get("hourly") or {}, multi.get("hourly") or {}, HOURLY, [recon] if recon else [])
    _average_block(data.get("daily") or {}, multi.get("daily") or {}, DAILY, [owm_days] if owm_days else [])
    y, my = data.get("yesterday") or {}, multi.get("yesterday") or {}
    for name, keys in (("hourly", HOURLY), ("daily", DAILY)):
        if y.get(name) and my.get(name):
            _average_block(y[name], my[name], keys)
    data["source"] = KEY
    data["members"] = MEMBERS + ([OWM] if owm_forecast is not None else [])
    today = ((data.get("daily") or {}).get("time") or [None])[0]
    data["spread_today"] = today_spread(multi, owm_days.get(today) if today else None)
    return data


def note(data: dict) -> str:
    """Подпись под прогнозом: «Среднее 4 источников (ECMWF, …), сегодня расходятся на 3°»."""
    from prefs import MODELS

    names = [MODELS.get(m, (m,))[0].split(" · ")[0] for m in data.get("members") or MEMBERS]
    text = f"Среднее {len(names)} источников ({', '.join(names)})"
    spread = data.get("spread_today")
    if spread is not None:
        text += ", сегодня " + ("почти не расходятся" if spread < 1.5 else f"расходятся до {round(spread)}°")
    return text
