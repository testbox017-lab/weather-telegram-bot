"""OpenWeatherMap (бесплатный API 2.5): текущая погода и прогноз на 5 дней с шагом 3 часа.

Ключ — переменная окружения OWM_API_KEY (бесплатно на openweathermap.org). Нет ключа или OWM
не ответил — бот показывает Open-Meteo, как раньше.

OWM не умеет всего, что умеет Open-Meteo (восход, УФ, вчерашний день, прогноз дальше 5 дней),
поэтому данные OWM накладываются поверх ответа Open-Meteo: текущая погода — целиком из OWM,
по часам и по дням — там, где у OWM есть прогноз; остальное (6–7 дни, солнце, УФ) — из Open-Meteo.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta, timezone

import aiohttp

KEY = "owm"  # значение настройки prefs "model"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
MIN_HOURS = 6  # день считаем по OWM, если OWM даёт хотя бы столько часов этого дня
MODELS_HOURS = 18  # в /models — только почти полные дни, иначе максимум и минимум занижены


class NoKey(Exception):
    """OWM_API_KEY не задан."""


def api_key() -> str:
    return os.getenv("OWM_API_KEY", "").strip()


def failure_text(e: Exception) -> str:
    """Причина сбоя для лога — без URL: в нём ключ."""
    if isinstance(e, aiohttp.ClientResponseError):
        return {401: "неверный или ещё не активированный ключ (401)", 429: "превышен лимит запросов (429)"}.get(
            e.status, f"HTTP {e.status}")
    return type(e).__name__


def wmo_code(owm_id: int | None) -> int | None:
    """Код погоды OWM (https://openweathermap.org/weather-conditions) → код WMO, как у Open-Meteo."""
    if owm_id is None:
        return None
    exact = {300: 51, 310: 51, 301: 53, 311: 53, 313: 53, 321: 53, 302: 55, 312: 55, 314: 55,
             500: 61, 501: 63, 511: 66, 520: 80, 521: 81, 522: 82, 531: 82,
             600: 71, 601: 73, 602: 75, 620: 85, 621: 85, 622: 86,
             800: 0, 801: 1, 802: 2, 803: 3, 804: 3}
    if owm_id in exact:
        return exact[owm_id]
    group = owm_id // 100
    if group == 2:
        return 95
    if 502 <= owm_id <= 504:
        return 65
    if 611 <= owm_id <= 616:  # мокрый снег, дождь со снегом
        return 71
    return {3: 53, 5: 63, 6: 73, 7: 45, 8: 3}.get(group)


def dew_point(t: float | None, rh: float | None) -> float | None:
    """Точка росы по формуле Магнуса."""
    if t is None or not rh:
        return None
    a, b = 17.62, 243.12
    g = math.log(rh / 100) + a * t / (b + t)
    return b * g / (a - g)


def _precip(item: dict, period: str) -> float:
    return sum((item.get(k) or {}).get(period) or 0 for k in ("rain", "snow"))


def parse_current(cur: dict) -> dict:
    """Ответ /weather → поля current в обозначениях Open-Meteo (только те, что есть у OWM)."""
    main, wind = cur.get("main") or {}, cur.get("wind") or {}
    out = {
        "temperature_2m": main.get("temp"),
        "apparent_temperature": main.get("feels_like"),
        "relative_humidity_2m": main.get("humidity"),
        "pressure_msl": main.get("sea_level") or main.get("pressure"),
        "wind_speed_10m": wind.get("speed"),
        "wind_direction_10m": wind.get("deg"),
        "wind_gusts_10m": wind.get("gust"),
        "cloud_cover": (cur.get("clouds") or {}).get("all"),
        "visibility": cur.get("visibility"),
        "weather_code": wmo_code(((cur.get("weather") or [{}])[0]).get("id")),
        "precipitation": _precip(cur, "1h"),
    }
    out["dew_point_2m"] = dew_point(out["temperature_2m"], out["relative_humidity_2m"])
    return {k: v for k, v in out.items() if v is not None}


def _local(dt: int, offset: int) -> datetime:
    return datetime.fromtimestamp(dt + offset, timezone.utc).replace(tzinfo=None)


def hourly(forecast: dict, offset: int) -> dict[str, dict]:
    """Прогноз OWM (шаг 3 часа) → по часам: "2026-11-16T14:00" → поля hourly в обозначениях Open-Meteo.

    offset — смещение местного времени, секунд (utc_offset_seconds из ответа Open-Meteo), чтобы часы
    совпали с часами Open-Meteo. Температура, влажность и ветер — линейно между точками OWM;
    погода, направление ветра и вероятность осадков — от ближайшей точки; осадки за 3 часа делятся на 3.
    """
    pts = []
    for item in forecast.get("list") or []:
        main, wind = item.get("main") or {}, item.get("wind") or {}
        if item.get("dt") is None or main.get("temp") is None:
            continue
        pts.append((_local(item["dt"], offset), {
            "temperature_2m": main["temp"], "relative_humidity_2m": main.get("humidity"),
            "wind_speed_10m": wind.get("speed"), "wind_gusts_10m": wind.get("gust"),
            "wind_direction_10m": wind.get("deg"),
            "weather_code": wmo_code(((item.get("weather") or [{}])[0]).get("id")),
            "precipitation": round(_precip(item, "3h") / 3, 2),
            "precipitation_probability": round((item.get("pop") or 0) * 100),
        }))
    pts.sort(key=lambda p: p[0])
    if not pts:
        return {}
    out = {}
    t = pts[0][0].replace(minute=0, second=0) + (timedelta(hours=1) if pts[0][0].minute else timedelta())
    j = 0
    while t <= pts[-1][0]:
        while j + 1 < len(pts) and pts[j + 1][0] <= t:
            j += 1
        (t0, a), (t1, b) = pts[j], pts[min(j + 1, len(pts) - 1)]
        span = (t1 - t0).total_seconds()
        w = (t - t0).total_seconds() / span if span else 0.0
        near = b if w > 0.5 else a
        row = dict(near)
        for k in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_gusts_10m"):
            if a.get(k) is not None and b.get(k) is not None:
                row[k] = round(a[k] + (b[k] - a[k]) * w, 1)
        if row.get("relative_humidity_2m") is not None:
            row["relative_humidity_2m"] = round(row["relative_humidity_2m"])
        dp = dew_point(row["temperature_2m"], row.get("relative_humidity_2m"))
        if dp is not None:
            row["dew_point_2m"] = round(dp, 1)
        out[t.strftime("%Y-%m-%dT%H:%M")] = row
        t += timedelta(hours=1)
    return out


def _day_rows(day: str, recon: dict, block: dict) -> tuple[list[dict], int]:
    """Часы дня day: из OWM, где он есть, иначе из hourly Open-Meteo. Второе — сколько часов из OWM."""
    rows, owm_hours = {}, 0
    times = block.get("time") or []
    for i, t in enumerate(times):
        if t.startswith(day):
            rows[t] = {k: v[i] for k, v in block.items() if isinstance(v, list) and i < len(v)}
    for t, row in recon.items():
        if t.startswith(day):
            rows[t] = row
            owm_hours += 1
    return list(rows.values()), owm_hours


def _vals(rows: list[dict], key: str) -> list:
    return [r[key] for r in rows if r.get(key) is not None]


def overlay(data: dict, current: dict, forecast: dict) -> dict:
    """Наложить данные OWM на ответ Open-Meteo (после weather.split_yesterday). Меняет и возвращает data."""
    offset = int(data.get("utc_offset_seconds") or 0)
    cur = data.setdefault("current", {})
    cur.update(parse_current(current))
    recon = hourly(forecast, offset)
    block = data.get("hourly") or {}
    times = block.get("time") or []
    for i, t in enumerate(times):
        row = recon.get(t)
        if not row:
            continue
        for k, v in row.items():
            if k in block and isinstance(block[k], list) and i < len(block[k]) and v is not None:
                block[k][i] = v
    daily = data.get("daily") or {}
    for i, day in enumerate(daily.get("time") or []):
        rows, owm_hours = _day_rows(day, recon, block)
        if owm_hours < MIN_HOURS:
            continue
        stats = {
            "temperature_2m_max": max(_vals(rows, "temperature_2m"), default=None),
            "temperature_2m_min": min(_vals(rows, "temperature_2m"), default=None),
            "precipitation_sum": round(sum(_vals(rows, "precipitation")), 1),
            "precipitation_probability_max": max(_vals(rows, "precipitation_probability"), default=None),
            "weather_code": max(_vals(rows, "weather_code"), default=None),
            "wind_speed_10m_max": max(_vals(rows, "wind_speed_10m"), default=None),
            "wind_gusts_10m_max": max(_vals(rows, "wind_gusts_10m"), default=None),
        }
        for k, v in stats.items():
            if v is not None and isinstance(daily.get(k), list) and i < len(daily[k]):
                daily[k][i] = v
    data["source"] = KEY
    return data


def add_series(data: dict, forecast: dict) -> dict:
    """Для /models: ряды OWM рядом с моделями Open-Meteo (ключи temperature_2m_owm и т. п., spread.py)."""
    recon = hourly(forecast, int(data.get("utc_offset_seconds") or 0))
    block = data.setdefault("hourly", {})
    block[f"temperature_2m_{KEY}"] = [(recon.get(t) or {}).get("temperature_2m") for t in block.get("time") or []]
    daily = data.setdefault("daily", {})
    hi, lo, prec = [], [], []
    for day in daily.get("time") or []:
        rows = [r for t, r in recon.items() if t.startswith(day)]
        full = len(rows) >= MODELS_HOURS
        hi.append(max(_vals(rows, "temperature_2m")) if full else None)
        lo.append(min(_vals(rows, "temperature_2m")) if full else None)
        prec.append(round(sum(_vals(rows, "precipitation")), 1) if full else None)
    daily[f"temperature_2m_max_{KEY}"], daily[f"temperature_2m_min_{KEY}"] = hi, lo
    daily[f"precipitation_sum_{KEY}"] = prec
    return data


def log_failure(e: Exception) -> None:
    if isinstance(e, NoKey):
        logging.warning("OpenWeatherMap: OWM_API_KEY не задан — показываю Open-Meteo")
    else:
        logging.warning("OpenWeatherMap недоступен (%s) — показываю Open-Meteo", failure_text(e))
