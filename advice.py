"""Совет по одежде по ощущаемой температуре, ветру, осадкам и УФ-индексу (простые правила)."""
from i18n import N_, _

SNOW_CODES = {71, 73, 75, 77, 85, 86}

# (ощущается не выше, что надеть)
LAYERS = [
    (-15, N_("пуховик, шапка, шарф и варежки")),
    (-5, N_("зимняя куртка, шапка и перчатки")),
    (5, N_("тёплая куртка и шапка")),
    (12, N_("куртка или пальто")),
    (18, N_("лёгкая куртка или свитер")),
    (24, N_("футболка, на вечер кофта")),
]


def upcoming(data: dict, hours: int = 12) -> list[dict]:
    """Почасовые данные начиная с текущего часа: [{time, temp, prec, prob, code, wind, gust}, …]."""
    h, cur = data.get("hourly") or {}, data.get("current") or {}
    times = h.get("time") or []
    if not times or not cur.get("time"):
        return []
    now = cur["time"][:13]
    start = next((i for i, t in enumerate(times) if t[:13] >= now), None)
    if start is None:
        return []

    def col(key):
        v = h.get(key) or []
        return lambda i: v[i] if i < len(v) else None

    temp, prec, prob, code = col("temperature_2m"), col("precipitation"), col("precipitation_probability"), \
        col("weather_code")
    wind, gust = col("wind_speed_10m"), col("wind_gusts_10m")
    return [{"time": times[i], "temp": temp(i), "prec": prec(i), "prob": prob(i), "code": code(i),
             "wind": wind(i), "gust": gust(i)} for i in range(start, min(start + hours, len(times)))]


def is_wet(hour: dict) -> bool:
    return (hour.get("prec") or 0) >= 0.1 or (hour.get("prob") or 0) >= 60


def clothing(data: dict) -> str | None:
    """«👕 Тёплая куртка и шапка, зонт» или None, если нет текущих данных."""
    cur = data.get("current") or {}
    feels = cur.get("apparent_temperature")
    if feels is None:
        return None
    base = _(next((text for limit, text in LAYERS if feels <= limit), N_("лёгкая одежда, пейте больше воды")))
    extra = []
    hours = upcoming(data, 12)
    wet = [h for h in hours if is_wet(h)] or ([cur] if (cur.get("precipitation") or 0) >= 0.1 else [])
    winds = [cur.get("wind_speed_10m") or 0] + [h["wind"] or 0 for h in hours]
    gusts = [cur.get("wind_gusts_10m") or 0] + [h["gust"] or 0 for h in hours]
    windy = max(winds) >= 10 or max(gusts) >= 15
    snow = any(h.get("code", h.get("weather_code")) in SNOW_CODES for h in wet)
    if wet and snow:
        extra.append(_("непромокаемая обувь"))
    elif wet:
        extra.append(_("капюшон или дождевик — зонт вывернет ветром") if windy else _("зонт"))
    if windy and not (wet and not snow):
        extra.append(_("одежда от ветра"))
    uv = ((data.get("daily") or {}).get("uv_index_max") or [None])[0]
    if uv is not None and uv >= 6:
        extra.append(_("крем от солнца и очки"))
    text = ", ".join([base] + extra)
    return f"👕 {text[0].upper()}{text[1:]}"


def dew_tips(data: dict) -> list[str]:
    """Советы по точке росы: духота, туман, гололёд. Пусто, если ничего примечательного."""
    cur = data.get("current") or {}
    t, dew = cur.get("temperature_2m"), cur.get("dew_point_2m")
    if t is None or dew is None:
        return []
    tips = []
    if dew >= 21:
        tips.append(_("🥵 Очень душно: точка росы {d}°", d=round(dew)))
    elif dew >= 18:
        tips.append(_("😓 Душно: точка росы {d}°", d=round(dew)))
    hours = upcoming(data, 12)
    wind = cur.get("wind_speed_10m") or 0
    if t - dew <= 1 and wind < 3 and cur.get("weather_code") not in (45, 48):
        tips.append(_("🌫 Воздух почти насыщен влагой — возможен туман"))
    temps = [h["temp"] for h in hours if h["temp"] is not None] + [t]
    cold = min(temps) <= 0 and max(temps) <= 3
    wet = any(is_wet(h) for h in hours) or (cur.get("precipitation") or 0) >= 0.1
    if cold and (wet or t - dew <= 1):
        tips.append(_("🧊 Около нуля и влажно — возможен гололёд, осторожно на дорогах и тротуарах"))

    return tips
