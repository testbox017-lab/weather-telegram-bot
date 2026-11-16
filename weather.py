"""Работа с Open-Meteo (ключ не нужен)."""
import asyncio
from dataclasses import dataclass

import aiohttp

from i18n import N_, _, geo_lang, wd

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
# OpenStreetMap: горы, станции, озёра, достопримечательности — когда геокодер Open-Meteo городов не нашёл.
# Правила Nominatim: свой User-Agent и не чаще запроса в секунду.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = "MyWeatherOpenMeteobot/1.0 (personal Telegram weather bot; github.com/testbox017-lab/weather-telegram-bot)"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: (N_("Ясно"), "☀️"), 1: (N_("Преимущественно ясно"), "🌤"), 2: (N_("Переменная облачность"), "⛅️"),
    3: (N_("Пасмурно"), "☁️"), 45: (N_("Туман"), "🌫"), 48: (N_("Изморозь"), "🌫"),
    51: (N_("Слабая морось"), "🌦"), 53: (N_("Морось"), "🌦"), 55: (N_("Сильная морось"), "🌧"),
    56: (N_("Ледяная морось"), "🌧"), 57: (N_("Сильная ледяная морось"), "🌧"),
    61: (N_("Небольшой дождь"), "🌦"), 63: (N_("Дождь"), "🌧"), 65: (N_("Сильный дождь"), "🌧"),
    66: (N_("Ледяной дождь"), "🌧"), 67: (N_("Сильный ледяной дождь"), "🌧"),
    71: (N_("Небольшой снег"), "🌨"), 73: (N_("Снег"), "🌨"), 75: (N_("Сильный снег"), "❄️"),
    77: (N_("Снежные зёрна"), "🌨"), 80: (N_("Небольшой ливень"), "🌦"), 81: (N_("Ливень"), "🌧"),
    82: (N_("Сильный ливень"), "⛈"), 85: (N_("Снегопад"), "🌨"), 86: (N_("Сильный снегопад"), "❄️"),
    95: (N_("Гроза"), "⛈"), 96: (N_("Гроза с градом"), "⛈"), 99: (N_("Сильная гроза с градом"), "⛈"),
}


def describe(code: int) -> str:
    text, emoji = WMO.get(code, (N_("Неизвестно"), "🌡"))
    return f"{emoji} {_(text)}"


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
        return {"models": model} if model and model not in ("best_match", "owm", "mean") else {}

    retry_delays = (1.0, 3.0)  # повторы при временных сбоях Open-Meteo (5xx, таймаут, обрыв связи)

    async def _get(self, url: str, params: dict, timeout: float = 10, headers: dict | None = None) -> dict:
        for attempt in range(len(self.retry_delays) + 1):
            try:
                extra = {"headers": headers} if headers else {}
                async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout),
                                            **extra) as r:
                    r.raise_for_status()
                    return await r.json()
            except (aiohttp.ClientResponseError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                temporary = not isinstance(e, aiohttp.ClientResponseError) or e.status >= 500 or e.status == 429
                if not temporary or attempt == len(self.retry_delays):
                    raise
                await asyncio.sleep(self.retry_delays[attempt])

    async def find_city(self, query: str) -> Place | None:
        places, _obvious = await self.find_cities(query)
        return places[0] if places else None

    async def find_cities(self, query: str) -> tuple[list[Place], bool]:
        """Все подходящие места (до geo.MAX_CHOICES) и признак «вариант очевиден, можно не спрашивать».

        После запятой можно уточнить регион или страну: «Бахмач, Черниговская».
        """
        from geo import candidates, split_query

        name = split_query(query)[0] or query
        data = await self._get(GEO_URL, {"name": name, "count": 20, "language": geo_lang(), "format": "json"})
        found = candidates(data.get("results") or [], query)
        if found[0]:
            return found
        try:
            return await self.find_osm(query)
        except Exception:  # OSM недоступен — как будто не нашли
            import logging

            logging.exception("nominatim error")
            return [], False

    _osm_lock = asyncio.Lock()
    _osm_last = 0.0

    async def find_osm(self, query: str) -> tuple[list[Place], bool]:
        """Поиск по OpenStreetMap (Nominatim): «Говерла», «вокзал Бахмач», «озеро Свитязь».

        В OSM слово «озеро» или «гора» часто не входит в название (украинское озеро — просто «Світязь»),
        поэтому, если нашлось меньше двух вариантов, ищем ещё раз без такого слова и показываем все.
        """
        from geo import osm_candidates, strip_kind_word

        rows = await self._nominatim(query)
        bare = strip_kind_word(query)
        if bare and len(osm_candidates(rows)[0]) < 2:
            rows += await self._nominatim(bare)
        return osm_candidates(rows)

    async def _nominatim(self, query: str) -> list:
        from geo import MAX_CHOICES

        async with WeatherClient._osm_lock:  # не чаще раза в секунду на весь бот
            loop = asyncio.get_running_loop()
            wait = WeatherClient._osm_last + 1.0 - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                data = await self._get(NOMINATIM_URL, {"q": query, "format": "jsonv2", "limit": MAX_CHOICES,
                                                       "accept-language": geo_lang()},
                                       headers={"User-Agent": NOMINATIM_UA})
            finally:
                WeatherClient._osm_last = loop.time()
        return data if isinstance(data, list) else []

    async def forecast(self, place: Place, days: int = 1) -> str:
        return format_forecast(place.name, await self.fetch(place, days), days)

    async def fetch(self, place: Place, days: int = 1) -> dict:
        """Сырые данные Open-Meteo: current, hourly (на 2 суток вперёд) и daily.

        Вчерашний день запрашивается тем же запросом (past_days=1) и выносится в data["yesterday"],
        чтобы hourly и daily, как и раньше, начинались с сегодняшнего дня.
        """
        params = {
            "latitude": place.lat,
            "longitude": place.lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,"
                       "wind_direction_10m,wind_gusts_10m,pressure_msl,cloud_cover,visibility,uv_index,"
                       "precipitation,is_day,dew_point_2m",
            "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,"
                      "wind_speed_10m,wind_gusts_10m,wind_direction_10m,relative_humidity_2m,dew_point_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "precipitation_sum,sunrise,sunset,daylight_duration,wind_speed_10m_max,"
                     "wind_gusts_10m_max,wind_direction_10m_dominant,relative_humidity_2m_mean,"
                     "relative_humidity_2m_min,relative_humidity_2m_max,uv_index_max",
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": max(days, 2),
            "past_days": 1,
            **self._model_param(),
        }
        model = self.model_hook()
        if model == "mean":
            return await self._fetch_mean(place, params)
        data = split_yesterday(await self._get(FORECAST_URL, params))
        if model == "owm":  # OpenWeatherMap поверх Open-Meteo; не вышло — остаётся Open-Meteo
            import owm

            try:
                current, fc = await self.fetch_owm(place)
                owm.overlay(data, current, fc)
            except Exception as e:
                owm.log_failure(e)
                data["source"] = "owm_failed"
        return data

    async def _fetch_mean(self, place: Place, params: dict) -> dict:
        """Режим «Среднее» (ensemble.py): «Авто» + ECMWF/ICON/GFS одним запросом + OWM, если есть ключ.
        Не ответили модели — обычный «Авто»; не ответил OWM — среднее трёх моделей."""
        import ensemble
        import owm

        async def owm_or_none():
            if not owm.api_key():
                return None
            try:
                return await self.fetch_owm(place)
            except Exception as e:
                owm.log_failure(e)
                return None

        base, multi, owm_data = await asyncio.gather(
            self._get(FORECAST_URL, params),
            self._get(FORECAST_URL, {**params, "models": ",".join(ensemble.MEMBERS)}),
            owm_or_none(), return_exceptions=True)
        if isinstance(base, BaseException):
            raise base
        data = split_yesterday(base)
        if isinstance(multi, BaseException):
            import logging

            logging.warning("Среднее: модели не ответили (%s) — показываю «Авто»", type(multi).__name__)
            data["source"] = "mean_failed"
            return data
        cur_fc = owm_data if isinstance(owm_data, (list, tuple)) else (None, None)
        return ensemble.apply(data, split_yesterday(multi), *cur_fc)

    async def fetch_owm(self, place: Place) -> tuple[dict, dict]:
        """Текущая погода и прогноз на 5 дней OpenWeatherMap (owm.py); нет ключа — owm.NoKey."""
        import owm

        key = owm.api_key()
        if not key:
            raise owm.NoKey()
        params = {"lat": place.lat, "lon": place.lon, "appid": key, "units": "metric"}
        return await asyncio.gather(self._get(owm.CURRENT_URL, params), self._get(owm.FORECAST_URL, params))

    async def fetch_models(self, place: Place, models: list[str], days: int = 7) -> dict:
        """Прогноз сразу нескольких моделей: ключи вида temperature_2m_max_ecmwf_ifs025 (spread.py)."""
        return await self._get(FORECAST_URL, {
            "latitude": place.lat, "longitude": place.lon, "timezone": "auto", "forecast_days": days,
            "hourly": "temperature_2m", "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "models": ",".join(models),
        })

    async def fetch_nowcast(self, place: Place) -> dict:
        """Осадки с шагом 15 минут на сегодня и завтра (radar.nowcast_text отбирает ближайшие часы)."""
        return await self._get(FORECAST_URL, {
            "latitude": place.lat, "longitude": place.lon, "timezone": "auto", "forecast_days": 2,
            "current": "precipitation", "minutely_15": "precipitation,snowfall",
        })

    async def fetch_past(self, place: Place, days: int = 7) -> dict:
        """Фактическая погода за прошедшие дни (анализ Open-Meteo): daily за days суток до сегодня."""
        data = await self._get(FORECAST_URL, {
            "latitude": place.lat, "longitude": place.lon, "timezone": "auto", "past_days": days,
            "forecast_days": 1, "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        })
        daily = data.get("daily") or {}
        data["daily"] = {k: v[:days] for k, v in daily.items()}  # последний элемент — сегодня, он не нужен
        return data

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
    lines = [_("📅 <b>Погода на {wd} {day:%d.%m.%Y}</b> — {name}", wd=wd(day.weekday()), day=day, name=name)]
    if archive:
        lines.append(_("<i>фактические данные (архив)</i>"))
    lines.append("")
    code = _first(d, "weather_code")
    if code is not None:
        lines.append(describe(code))
    tmin, tmax = _first(d, "temperature_2m_min"), _first(d, "temperature_2m_max")
    if tmin is None or tmax is None:
        return "\n".join(lines + [_("Нет данных за эту дату 🤷")])
    lines.append(f"🌡 {round(tmin)}…{round(tmax)}°C")
    rain, prob = _first(d, "precipitation_sum"), _first(d, "precipitation_probability_max")
    if rain is not None:
        line = _("☔️ Осадки: {rain:.1f} мм", rain=rain)
        if prob is not None:
            line += _(", вероятность {prob}%", prob=prob)
        lines.append(line)
    wind, gust = _first(d, "wind_speed_10m_max"), _first(d, "wind_gusts_10m_max")
    if wind is not None:
        lines.append(_("💨 Ветер до {wind:.1f} м/с", wind=wind)
                     + (_(", порывы до {gust:.1f} м/с", gust=gust) if gust is not None else ""))
    hum = _first(d, "relative_humidity_2m_mean")
    if hum is not None:
        hlo, hhi = _first(d, "relative_humidity_2m_min"), _first(d, "relative_humidity_2m_max")
        rng = f" ({round(hlo)}–{round(hhi)}%)" if hlo is not None and hhi is not None else ""
        lines.append(_("💧 Влажность: {hum}%{rng}", hum=round(hum), rng=rng))
    return "\n".join(lines)


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


DIRS = [(N_("северный"), "↓"), (N_("северо-восточный"), "↙"), (N_("восточный"), "←"), (N_("юго-восточный"), "↖"),
        (N_("южный"), "↑"), (N_("юго-западный"), "↗"), (N_("западный"), "→"), (N_("северо-западный"), "↘")]


def wind_dir(deg: float | None) -> str:
    """Откуда дует ветер словами и стрелкой, куда он дует: 200° → «↗ юго-западный»."""
    if deg is None:
        return ""
    name, arrow = DIRS[round(deg % 360 / 45) % 8]
    return f"{arrow} {_(name)}"


def uv_text(uv: float | None) -> str | None:
    if uv is None:
        return None
    uv = round(uv)
    if uv <= 2:
        level = _("низкий")
    elif uv <= 5:
        level = _("умеренный, нужен крем SPF 30")
    elif uv <= 7:
        level = _("высокий, крем SPF 50 и головной убор")
    elif uv <= 10:
        level = _("очень высокий, избегайте солнца в полдень")
    else:
        level = _("экстремальный, лучше не выходить на солнце")
    return _("🕶 УФ-индекс до {uv} — {level}", uv=uv, level=level)


def visibility_text(m: float | None) -> str | None:
    if m is None:
        return None
    if m >= 10_000:
        return None  # хорошую видимость не показываем, чтобы не засорять сводку
    shown = _("{km:.1f} км", km=m / 1000) if m >= 1000 else _("{m} м", m=round(m))
    return _("👁 Видимость {shown}", shown=shown) + (_(" — туман") if m < 1000 else "")


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

    def hh(i: int) -> str:
        return times[i][11:16]

    if (cur.get("precipitation") or 0) >= 0.1 or (wet and wet[0]):
        first = idx[0]
        stop = next((idx[j] for j, w in enumerate(wet) if not w), None)
        snow = cur.get("weather_code") in SNOW_CODES or codes[first] in SNOW_CODES
        if stop is None:
            return (_("☔️ Снег идёт и не прекратится ближайшие {n} ч", n=len(idx)) if snow else
                    _("☔️ Дождь идёт и не прекратится ближайшие {n} ч", n=len(idx)))
        return (_("☔️ Снег идёт, закончится около {t}", t=hh(stop)) if snow else
                _("☔️ Дождь идёт, закончится около {t}", t=hh(stop)))
    first_wet = next((idx[j] for j, w in enumerate(wet) if w), None)
    if first_wet is None:
        return _("🌂 Без осадков ближайшие {n} ч", n=len(idx))
    p = prob[first_wet]
    chance = _(" (вероятность {p}%)", p=p) if p is not None else ""
    if codes[first_wet] in SNOW_CODES:
        return _("☔️ Снег начнётся около {t}{chance}", t=hh(first_wet), chance=chance)
    return _("☔️ Дождь начнётся около {t}{chance}", t=hh(first_wet), chance=chance)


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
        return _("↔️ Так же, как вчера в это время")
    if diff > 0:
        return _("🔺 На {n}° теплее, чем вчера в это время", n=diff)
    return _("🔻 На {n}° холоднее, чем вчера в это время", n=-diff)


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
    from advice import dew_tips

    lines += dew_tips(data)
    lines += [
        "",
        f"{describe(cur['weather_code'])}",
        _("🌡 {t}°C (ощущается как {feels}°C)", t=round(cur['temperature_2m']),
          feels=round(cur['apparent_temperature'])),
    ]
    compare = yesterday_text(data)
    if compare:
        lines.append(compare)
    humidity = _("💧 Влажность: {hum}%", hum=cur['relative_humidity_2m'])
    if cur.get("dew_point_2m") is not None:
        humidity += _(", точка росы {dew}°", dew=round(cur['dew_point_2m']))
    lines.append(humidity)
    wind = _("💨 Ветер: {wind:.1f} м/с", wind=cur['wind_speed_10m'])
    direction = wind_dir(cur.get("wind_direction_10m"))
    if direction:
        wind += f", {direction}"
    gust = cur.get("wind_gusts_10m")
    if gust is not None and gust >= cur["wind_speed_10m"] + 2:
        wind += _(", порывы до {gust:.0f} м/с", gust=gust)
    lines.append(wind)
    if cur.get("pressure_msl") is not None:
        lines.append(_("🧭 Давление: {p} мм рт. ст.", p=round(cur['pressure_msl'] * 0.750062)))
    if cur.get("cloud_cover") is not None:
        lines.append(_("☁️ Облачность: {c}%", c=cur['cloud_cover']))
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
            lines.append("\n" + _("Сегодня: {lo}…{hi}°C, вероятность осадков {p}%",
                                  lo=round(d['temperature_2m_min'][0]), hi=round(d['temperature_2m_max'][0]),
                                  p=d['precipitation_probability_max'][0] or 0))
        else:
            lines.append("\n" + _("<b>Прогноз на {n} дн.:</b>", n=days))
            for i, day in enumerate(d["time"][:days]):
                dt = date.fromisoformat(day)
                code = d["weather_code"][i]
                emoji = WMO.get(code, ("", "🌡"))[1]
                line = (
                    f"{wd(dt.weekday())} {dt:%d.%m}: {emoji} "
                    f"{round(d['temperature_2m_min'][i])}…{round(d['temperature_2m_max'][i])}°C, "
                    f"☔️ {d['precipitation_probability_max'][i] or 0}%"
                )
                wind = d.get("wind_speed_10m_max")
                if wind and wind[i] is not None:
                    line += _(", 💨 {w} м/с", w=round(wind[i]))
                lines.append(line)
    return "\n".join(lines)


# Что можно показать в краткой сводке (выбирается в /settings); по умолчанию — как было раньше
SHORT_FIELDS = {
    "now": N_("Погода и температура"),
    "feels": N_("Ощущается"),
    "wind": N_("Ветер"),
    "humidity": N_("Влажность"),
    "pressure": N_("Давление"),
    "rain": N_("Осадки на 12 ч"),
    "today": N_("Сегодня мин…макс"),
    "advice": N_("Что надеть"),
}
SHORT_DEFAULT = ["now", "feels", "wind", "rain", "today"]


def format_short(name: str, data: dict, fields: list[str] | None = None) -> str:
    """Краткая сводка в несколько строк (для частых рассылок); fields — какие части показать."""
    on = set(SHORT_DEFAULT if fields is None else fields)
    cur = data["current"]
    parts = []
    feels = cur.get("apparent_temperature") if "feels" in on else None
    if "now" in on:
        now = f"{describe(cur['weather_code'])}, {round(cur['temperature_2m'])}°C"
        parts.append(now + (_(" (ощущается {f}°)", f=round(feels)) if feels is not None else ""))
    elif feels is not None:
        parts.append(_("ощущается {f}°", f=round(feels)))
    if "wind" in on and cur.get("wind_speed_10m") is not None:
        parts.append(_("💨 {w:.0f} м/с", w=cur['wind_speed_10m']))
    if "humidity" in on and cur.get("relative_humidity_2m") is not None:
        parts.append(f"💧 {cur['relative_humidity_2m']}%")
    if "pressure" in on and cur.get("pressure_msl") is not None:
        parts.append(_("🧭 {p} мм", p=round(cur['pressure_msl'] * 0.750062)))
    lines = [f"📍 <b>{name}</b>" + (": " + ", ".join(parts) if parts else "")]
    if "rain" in on:
        outlook = rain_outlook(data)
        if outlook:
            lines.append(outlook)
    d = data.get("daily") or {}
    tmin, tmax = _first(d, "temperature_2m_min"), _first(d, "temperature_2m_max")
    if "today" in on and tmin is not None and tmax is not None:
        prob = _first(d, "precipitation_probability_max")
        lines.append(_("Сегодня {lo}…{hi}°C", lo=round(tmin), hi=round(tmax))
                     + (f", ☔️ {prob}%" if prob is not None else ""))
    if "advice" in on:
        from advice import clothing

        tip = clothing(data)
        if tip:
            lines.append(tip)
    return "\n".join(lines)


def format_hourly(name: str, data: dict, hours: int = 12) -> str:
    """Ближайшие часы строками: «15:00 ☁️ +7°, ☔️ 40% 0.3 мм, 💨 3 м/с»."""
    from advice import upcoming

    rows = upcoming(data, hours)
    if not rows:
        return f"📍 <b>{name}</b>\n" + _("Нет почасовых данных 🤷")
    lines = [_("⏱ <b>{name}</b> — по часам", name=name), ""]
    for h in rows:
        emoji = WMO.get(h["code"], ("", "🌡"))[1] if h["code"] is not None else "🌡"
        t = h["temp"]
        line = f"{h['time'][11:16]} {emoji} {'+' if t is not None and round(t) > 0 else ''}{round(t) if t is not None else '?'}°"
        if h["prob"] is not None:
            line += f", ☔️ {h['prob']}%"
        if (h["prec"] or 0) >= 0.1:
            line += _(" {mm:.1f} мм", mm=h['prec'])
        if h["wind"] is not None:
            line += _(", 💨 {w} м/с", w=round(h['wind']))

        lines.append(line)
    return "\n".join(lines)
