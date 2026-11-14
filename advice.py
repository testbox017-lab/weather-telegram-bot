"""Совет по одежде по ощущаемой температуре, ветру, осадкам и УФ-индексу (простые правила)."""

SNOW_CODES = {71, 73, 75, 77, 85, 86}

# (ощущается не выше, что надеть)
LAYERS = [
    (-15, "пуховик, шапка, шарф и варежки"),
    (-5, "зимняя куртка, шапка и перчатки"),
    (5, "тёплая куртка и шапка"),
    (12, "куртка или пальто"),
    (18, "лёгкая куртка или свитер"),
    (24, "футболка, на вечер кофта"),
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
    base = next((text for limit, text in LAYERS if feels <= limit), "лёгкая одежда, пейте больше воды")
    extra = []
    hours = upcoming(data, 12)
    wet = [h for h in hours if is_wet(h)] or ([cur] if (cur.get("precipitation") or 0) >= 0.1 else [])
    winds = [cur.get("wind_speed_10m") or 0] + [h["wind"] or 0 for h in hours]
    gusts = [cur.get("wind_gusts_10m") or 0] + [h["gust"] or 0 for h in hours]
    windy = max(winds) >= 10 or max(gusts) >= 15
    snow = any(h.get("code", h.get("weather_code")) in SNOW_CODES for h in wet)
    if wet and snow:
        extra.append("непромокаемая обувь")
    elif wet:
        extra.append("капюшон или дождевик — зонт вывернет ветром" if windy else "зонт")
    if windy and not (wet and not snow):
        extra.append("одежда от ветра")
    uv = ((data.get("daily") or {}).get("uv_index_max") or [None])[0]
    if uv is not None and uv >= 6:
        extra.append("крем от солнца и очки")
    text = ", ".join([base] + extra)
    return f"👕 {text[0].upper()}{text[1:]}"
