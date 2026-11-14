"""Работа с Open-Meteo (ключ не нужен)."""
import asyncio
from dataclasses import dataclass

import aiohttp

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: ("Ясно", "☀️"), 1: ("Преимущественно ясно", "🌤"), 2: ("Переменная облачность", "⛅️"),
    3: ("Пасмурно", "☁️"), 45: ("Туман", "🌫"), 48: ("Изморозь", "🌫"),
    51: ("Слабая морось", "🌦"), 53: ("Морось", "🌦"), 55: ("Сильная морось", "🌧"),
    56: ("Ледяная морось", "🌧"), 57: ("Сильная ледяная морось", "🌧"),
    61: ("Небольшой дождь", "🌦"), 63: ("Дождь", "🌧"), 65: ("Сильный дождь", "🌧"),
    66: ("Ледяной дождь", "🌧"), 67: ("Сильный ледяной дождь", "🌧"),
    71: ("Небольшой снег", "🌨"), 73: ("Снег", "🌨"), 75: ("Сильный снег", "❄️"),
    77: ("Снежные зёрна", "🌨"), 80: ("Небольшой ливень", "🌦"), 81: ("Ливень", "🌧"),
    82: ("Сильный ливень", "⛈"), 85: ("Снегопад", "🌨"), 86: ("Сильный снегопад", "❄️"),
    95: ("Гроза", "⛈"), 96: ("Гроза с градом", "⛈"), 99: ("Сильная гроза с градом", "⛈"),
}


def describe(code: int) -> str:
    text, emoji = WMO.get(code, ("Неизвестно", "🌡"))
    return f"{emoji} {text}"


@dataclass
class Place:
    name: str
    lat: float
    lon: float


class WeatherClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    model_hook = staticmethod(lambda: None)  # модель прогноза текущего пользователя (prefs.MODELS), задаёт bot.main

    def _model_param(self) -> dict:
        model = self.model_hook()
        return {"models": model} if model and model != "best_match" else {}

    retry_delays = (1.0, 3.0)  # повторы при временных сбоях Open-Meteo (5xx, таймаут, обрыв связи)

    async def _get(self, url: str, params: dict, timeout: float = 10) -> dict:
        for attempt in range(len(self.retry_delays) + 1):
            try:
                async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                    r.raise_for_status()
                    return await r.json()
            except (aiohttp.ClientResponseError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                temporary = not isinstance(e, aiohttp.ClientResponseError) or e.status >= 500 or e.status == 429
                if not temporary or attempt == len(self.retry_delays):
                    raise
                await asyncio.sleep(self.retry_delays[attempt])

    async def find_city(self, query: str) -> Place | None:
        places, _ = await self.find_cities(query)
        return places[0] if places else None

    async def find_cities(self, query: str) -> tuple[list[Place], bool]:
        """Все подходящие места (до geo.MAX_CHOICES) и признак «вариант очевиден, можно не спрашивать».

        После запятой можно уточнить регион или страну: «Бахмач, Черниговская».
        """
        from geo import candidates, split_query

        name = split_query(query)[0] or query
        data = await self._get(GEO_URL, {"name": name, "count": 20, "language": "ru", "format": "json"})
        return candidates(data.get("results") or [], query)

    async def forecast(self, place: Place, days: int = 1) -> str:
        return format_forecast(place.name, await self.fetch(place, days), days)

    async def fetch(self, place: Place, days: int = 1) -> dict:
        """Сырые данные Open-Meteo: current, hourly (на 2 суток вперёд) и daily.

        Вчерашний день запрашивается тем же запросом (past_days=1) и выносится в data["yesterday"],
        чтобы hourly и daily, как и раньше, начинались с сегодняшнего дня.
        """
        data = await self._get(FORECAST_URL, {
            "latitude": place.lat,
            "longitude": place.lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,"
                       "wind_direction_10m,wind_gusts_10m,pressure_msl,cloud_cover,visibility,uv_index,"
                       "precipitation,is_day",
            "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,"
                      "wind_speed_10m,wind_gusts_10m,wind_direction_10m,relative_humidity_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "precipitation_sum,sunrise,sunset,daylight_duration,wind_speed_10m_max,"
                     "wind_gusts_10m_max,wind_direction_10m_dominant,relative_humidity_2m_mean,"
                     "relative_humidity_2m_min,relative_humidity_2m_max,uv_index_max",
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": max(days, 2),
            "past_days": 1,
            **self._model_param(),
        })
        return split_yesterday(data)

    async def fetch_waqi(self, place: Place, token: str) -> dict:
        """Ближайшая станция WAQI (aqicn.org): data из ответа API; ошибка API — ValueError."""
        from air import WAQI_URL

        resp = await self._get(WAQI_URL.format(lat=place.lat, lon=place.lon), {"token": token})
        if resp.get("status") != "ok" or not isinstance(resp.get("data"), dict):
            raise ValueError(f"WAQI: {resp.get('data')}")
        return resp["data"]

    async def fetch_air(self, place: Place) -> dict:
        """Качество воздуха и пыльца: current + почасовой индекс EAQI на 2 суток."""
        from air import AIR_URL, CURRENT

        return await self._get(AIR_URL, {"latitude": place.lat, "longitude": place.lon, "current": CURRENT,
                                         "hourly": "european_aqi", "forecast_days": 2, "timezone": "auto"})

    async def fetch_climate(self, lat: float, lon: float, from_year: int, to_year: int) -> dict:
        """Суточный архив за годы from_year…to_year (для климатической нормы)."""
        data = await self._get(ARCHIVE_URL, {
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "start_date": f"{from_year}-01-01", "end_date": f"{to_year}-12-31",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        }, timeout=60)
        return data.get("daily") or {}

    async def timezone(self, place: Place) -> str:
        """Часовой пояс места (IANA, например Europe/Kyiv) по данным Open-Meteo."""
        data = await self._get(FORECAST_URL, {"latitude": place.lat, "longitude": place.lon,
                                              "current": "temperature_2m", "timezone": "auto"})
        return data.get("timezone") or "UTC"

    async def fetch_day(self, place: Place, day, archive: bool = False) -> dict:
        """Почасовые (00–23) и суточные данные за одну дату: прогноз или архив."""
        hourly, daily = HOURLY_VARS, DAILY_VARS
        if archive:  # в архиве нет вероятности осадков
            hourly = [v for v in hourly if not v.startswith("precipitation_probability")]
            daily = [v for v in daily if not v.startswith("precipitation_probability")]
        return await self._get(ARCHIVE_URL if archive else FORECAST_URL, {
            "latitude": place.lat,
            "longitude": place.lon,
            "hourly": ",".join(hourly),
            "daily": ",".join(daily),
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            **({} if archive else self._model_param()),
        })


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = ["temperature_2m", "precipitation_probability", "precipitation", "wind_speed_10m",
               "wind_gusts_10m", "wind_direction_10m", "relative_humidity_2m"]
DAILY_VARS = ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max",
              "precipitation_sum", "sunrise", "sunset", "daylight_duration", "wind_speed_10m_max",
              "wind_gusts_10m_max", "wind_direction_10m_dominant", "relative_humidity_2m_mean",
              "relative_humidity_2m_min", "relative_humidity_2m_max"]


def _first(d: dict, key: str):
    v = d.get(key) or [None]
    return v[0]


def format_day(name: str, data: dict, day, archive: bool = False) -> str:
    """Сводка за одну дату (без блока «сейчас»)."""
    d = data.get("daily") or {}
    lines = [f"📅 <b>Погода на {DAYS_RU[day.weekday()]} {day:%d.%m.%Y}</b> — {name}"]
    if archive:
        lines.append("<i>фактические данные (архив)</i>")
    lines.append("")
    code = _first(d, "weather_code")
    if code is not None:
        lines.append(describe(code))
    tmin, tmax = _first(d, "temperature_2m_min"), _first(d, "temperature_2m_max")
    if tmin is None or tmax is None:
        return "\n".join(lines + ["Нет данных за эту дату 🤷"])
    lines.append(f"🌡 {round(tmin)}…{round(tmax)}°C")
    rain, prob = _first(d, "precipitation_sum"), _first(d, "precipitation_probability_max")
    if rain is not None:
        line = f"☔️ Осадки: {rain:.1f} мм"
        if prob is not None:
            line += f", вероятность {prob}%"
        lines.append(line)
    wind, gust = _first(d, "wind_speed_10m_max"), _first(d, "wind_gusts_10m_max")
    if wind is not None:
        lines.append(f"💨 Ветер до {wind:.1f} м/с" + (f", порывы до {gust:.1f} м/с" if gust is not None else ""))
    hum = _first(d, "relative_humidity_2m_mean")
    if hum is not None:
        hlo, hhi = _first(d, "relative_humidity_2m_min"), _first(d, "relative_humidity_2m_max")
        rng = f" ({round(hlo)}–{round(hhi)}%)" if hlo is not None and hhi is not None else ""
        lines.append(f"💧 Влажность: {round(hum)}%{rng}")
    return "\n".join(lines)


DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def split_yesterday(data: dict) -> dict:
    """Убирает из hourly/daily дни раньше сегодняшнего (past_days) и кладёт их в data["yesterday"]."""
    today = (data.get("current") or {}).get("time", "")[:10]
    if not today:
        return data
    yesterday = {}
    for key in ("hourly", "daily"):
        block = data.get(key)
        if not block or "time" not in block:
            continue
        cut = next((i for i, t in enumerate(block["time"]) if t[:10] >= today), len(block["time"]))
        if not cut:
            continue
        yesterday[key] = {k: v[:cut] for k, v in block.items() if isinstance(v, list)}
        data[key] = {k: (v[cut:] if isinstance(v, list) else v) for k, v in block.items()}
    if yesterday:
        data["yesterday"] = yesterday
    return data


DIRS = [("северный", "↓"), ("северо-восточный", "↙"), ("восточный", "←"), ("юго-восточный", "↖"),
        ("южный", "↑"), ("юго-западный", "↗"), ("западный", "→"), ("северо-западный", "↘")]


def wind_dir(deg: float | None) -> str:
    """Откуда дует ветер словами и стрелкой, куда он дует: 200° → «↗ юго-западный»."""
    if deg is None:
        return ""
    name, arrow = DIRS[round(deg % 360 / 45) % 8]
    return f"{arrow} {name}"


def uv_text(uv: float | None) -> str | None:
    if uv is None:
        return None
    uv = round(uv)
    if uv <= 2:
        level = "низкий"
    elif uv <= 5:
        level = "умеренный, нужен крем SPF 30"
    elif uv <= 7:
        level = "высокий, крем SPF 50 и головной убор"
    elif uv <= 10:
        level = "очень высокий, избегайте солнца в полдень"
    else:
        level = "экстремальный, лучше не выходить на солнце"
    return f"🕶 УФ-индекс до {uv} — {level}"


def visibility_text(m: float | None) -> str | None:
    if m is None:
        return None
    if m >= 10_000:
        return None  # хорошую видимость не показываем, чтобы не засорять сводку
    shown = f"{m / 1000:.1f} км" if m >= 1000 else f"{round(m)} м"
    return f"👁 Видимость {shown}" + (" — туман" if m < 1000 else "")


SNOW_CODES = {71, 73, 75, 77, 85, 86}


def _is_wet(prec, prob) -> bool:
    return (prec or 0) >= 0.1 or (prob or 0) >= 60


def rain_outlook(data: dict, hours: int = 12) -> str | None:
    """«☔️ Дождь начнётся около 16:00» / «Без осадков ближайшие 12 ч» по почасовым данным."""
    h, cur = data.get("hourly") or {}, data.get("current") or {}
    times = h.get("time") or []
    if not times or not cur.get("time"):
        return None
    now = cur["time"][:13]  # "2026-11-14T15"
    start = next((i for i, t in enumerate(times) if t[:13] >= now), None)
    if start is None:
        return None
    n = len(times)
    prec = (h.get("precipitation") or [None] * n)
    prob = (h.get("precipitation_probability") or [None] * n)
    codes = (h.get("weather_code") or [None] * n)
    idx = list(range(start, min(start + hours, n)))
    wet = [_is_wet(prec[i], prob[i]) for i in idx]

    def kind(i: int) -> str:
        return "снег" if codes[i] in SNOW_CODES else "дождь"

    def hh(i: int) -> str:
        return times[i][11:16]

    if (cur.get("precipitation") or 0) >= 0.1 or (wet and wet[0]):
        first = idx[0]
        stop = next((idx[j] for j, w in enumerate(wet) if not w), None)
        what = "Снег" if (cur.get("weather_code") in SNOW_CODES or codes[first] in SNOW_CODES) else "Дождь"
        if stop is None:
            return f"☔️ {what} идёт и не прекратится ближайшие {len(idx)} ч"
        return f"☔️ {what} идёт, закончится около {hh(stop)}"
    first_wet = next((idx[j] for j, w in enumerate(wet) if w), None)
    if first_wet is None:
        return f"🌂 Без осадков ближайшие {len(idx)} ч"
    p = prob[first_wet]
    chance = f" (вероятность {p}%)" if p is not None else ""
    return f"☔️ {kind(first_wet).capitalize()} начнётся около {hh(first_wet)}{chance}"


def yesterday_text(data: dict) -> str | None:
    """«На 4° теплее, чем вчера в это время» — сравнение текущей температуры со вчерашней."""
    cur = data.get("current") or {}
    y = (data.get("yesterday") or {}).get("hourly") or {}
    if cur.get("temperature_2m") is None or not cur.get("time") or not y.get("time"):
        return None
    hour = cur["time"][11:13]
    temps = y.get("temperature_2m") or []
    past = next((temps[i] for i, t in enumerate(y["time"]) if t[11:13] == hour and i < len(temps)), None)
    if past is None:
        return None
    diff = round(cur["temperature_2m"] - past)
    if diff == 0:
        return "↔️ Так же, как вчера в это время"
    word = "теплее" if diff > 0 else "холоднее"
    return f"{'🔺' if diff > 0 else '🔻'} На {abs(diff)}° {word}, чем вчера в это время"


def format_forecast(name: str, data: dict, days: int = 1) -> str:
    from datetime import date

    cur = data["current"]
    lines = [f"📍 <b>{name}</b>"]
    outlook = rain_outlook(data)
    if outlook:
        lines.append(outlook)
    from advice import clothing

    tip = clothing(data)
    if tip:
        lines.append(tip)
    lines += [
        "",
        f"{describe(cur['weather_code'])}",
        f"🌡 {round(cur['temperature_2m'])}°C (ощущается как {round(cur['apparent_temperature'])}°C)",
    ]
    compare = yesterday_text(data)
    if compare:
        lines.append(compare)
    lines.append(f"💧 Влажность: {cur['relative_humidity_2m']}%")
    wind = f"💨 Ветер: {cur['wind_speed_10m']:.1f} м/с"
    direction = wind_dir(cur.get("wind_direction_10m"))
    if direction:
        wind += f", {direction}"
    gust = cur.get("wind_gusts_10m")
    if gust is not None and gust >= cur["wind_speed_10m"] + 2:
        wind += f", порывы до {gust:.0f} м/с"
    lines.append(wind)
    if cur.get("pressure_msl") is not None:
        lines.append(f"🧭 Давление: {round(cur['pressure_msl'] * 0.750062)} мм рт. ст.")
    if cur.get("cloud_cover") is not None:
        lines.append(f"☁️ Облачность: {cur['cloud_cover']}%")
    vis = visibility_text(cur.get("visibility"))
    if vis:
        lines.append(vis)
    d = data.get("daily")
    uv_max = _first(d or {}, "uv_index_max")
    uv = uv_text(uv_max if uv_max is not None else cur.get("uv_index"))
    if uv:
        lines.append(uv)
    if d:
        if days <= 1:
            lines.append(
                f"\nСегодня: {round(d['temperature_2m_min'][0])}…{round(d['temperature_2m_max'][0])}°C, "
                f"вероятность осадков {d['precipitation_probability_max'][0] or 0}%"
            )
        else:
            lines.append(f"\n<b>Прогноз на {days} дн.:</b>")
            for i, day in enumerate(d["time"][:days]):
                dt = date.fromisoformat(day)
                code = d["weather_code"][i]
                emoji = WMO.get(code, ("", "🌡"))[1]
                line = (
                    f"{DAYS_RU[dt.weekday()]} {dt:%d.%m}: {emoji} "
                    f"{round(d['temperature_2m_min'][i])}…{round(d['temperature_2m_max'][i])}°C, "
                    f"☔️ {d['precipitation_probability_max'][i] or 0}%"
                )
                wind = d.get("wind_speed_10m_max")
                if wind and wind[i] is not None:
                    line += f", 💨 {round(wind[i])} м/с"
                lines.append(line)
    return "\n".join(lines)


def format_short(name: str, data: dict) -> str:
    """Краткая сводка в три строки (для частых рассылок)."""
    cur = data["current"]
    line1 = (f"📍 <b>{name}</b>: {describe(cur['weather_code'])}, {round(cur['temperature_2m'])}°C "
             f"(ощущается {round(cur['apparent_temperature'])}°), 💨 {cur['wind_speed_10m']:.0f} м/с")
    lines = [line1]
    outlook = rain_outlook(data)
    if outlook:
        lines.append(outlook)
    d = data.get("daily") or {}
    tmin, tmax = _first(d, "temperature_2m_min"), _first(d, "temperature_2m_max")
    if tmin is not None and tmax is not None:
        prob = _first(d, "precipitation_probability_max")
        lines.append(f"Сегодня {round(tmin)}…{round(tmax)}°C" + (f", ☔️ {prob}%" if prob is not None else ""))
    return "\n".join(lines)


def format_hourly(name: str, data: dict, hours: int = 12) -> str:
    """Ближайшие часы строками: «15:00 ☁️ +7°, ☔️ 40% 0.3 мм, 💨 3 м/с»."""
    from advice import upcoming

    rows = upcoming(data, hours)
    if not rows:
        return f"📍 <b>{name}</b>\nНет почасовых данных 🤷"
    lines = [f"⏱ <b>{name}</b> — по часам", ""]
    for h in rows:
        emoji = WMO.get(h["code"], ("", "🌡"))[1] if h["code"] is not None else "🌡"
        t = h["temp"]
        line = f"{h['time'][11:16]} {emoji} {'+' if t is not None and round(t) > 0 else ''}{round(t) if t is not None else '?'}°"
        if h["prob"] is not None:
            line += f", ☔️ {h['prob']}%"
        if (h["prec"] or 0) >= 0.1:
            line += f" {h['prec']:.1f} мм"
        if h["wind"] is not None:
            line += f", 💨 {round(h['wind'])} м/с"
        lines.append(line)
    return "\n".join(lines)
