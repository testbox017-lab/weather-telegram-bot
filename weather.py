"""Работа с Open-Meteo (ключ не нужен)."""
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

    async def _get(self, url: str, params: dict) -> dict:
        async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            r.raise_for_status()
            return await r.json()

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
        """Сырые данные Open-Meteo: current, hourly (на 2 суток вперёд) и daily."""
        return await self._get(FORECAST_URL, {
            "latitude": place.lat,
            "longitude": place.lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "hourly": "temperature_2m,precipitation_probability,precipitation,"
                      "wind_speed_10m,wind_gusts_10m,wind_direction_10m,relative_humidity_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "precipitation_sum,sunrise,sunset,daylight_duration,wind_speed_10m_max,"
                     "wind_gusts_10m_max,wind_direction_10m_dominant,relative_humidity_2m_mean,"
                     "relative_humidity_2m_min,relative_humidity_2m_max",
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": max(days, 2),
        })

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


def format_forecast(name: str, data: dict, days: int = 1) -> str:
    from datetime import date

    cur = data["current"]
    lines = [
        f"📍 <b>{name}</b>",
        "",
        f"{describe(cur['weather_code'])}",
        f"🌡 {round(cur['temperature_2m'])}°C (ощущается как {round(cur['apparent_temperature'])}°C)",
        f"💧 Влажность: {cur['relative_humidity_2m']}%",
        f"💨 Ветер: {cur['wind_speed_10m']:.1f} м/с",
    ]
    d = data.get("daily")
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
