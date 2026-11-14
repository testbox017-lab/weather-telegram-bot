"""Качество воздуха и пыльца (Open-Meteo Air Quality API, модели CAMS)."""
from __future__ import annotations

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
POLLEN = {  # переменная → (название, пороги «низкая/средняя/высокая», зёрен/м³)
    "birch_pollen": ("берёза", (10, 100, 500)),
    "alder_pollen": ("ольха", (10, 100, 500)),
    "grass_pollen": ("злаки", (5, 30, 100)),
    "mugwort_pollen": ("полынь", (5, 30, 100)),
    "ragweed_pollen": ("амброзия", (5, 20, 50)),
    "olive_pollen": ("олива", (10, 100, 500)),
}
CURRENT = "european_aqi,pm2_5,pm10,nitrogen_dioxide,ozone," + ",".join(POLLEN)
# Европейский индекс качества воздуха (EAQI): верхняя граница → оценка
AQI_LEVELS = [(20, "🟢", "хороший"), (40, "🟢", "приемлемый"), (60, "🟡", "умеренный"),
              (80, "🟠", "плохой"), (100, "🔴", "очень плохой"), (float("inf"), "🟣", "крайне плохой")]
AQI_ADVICE = {
    "умеренный": "Чувствительным людям лучше сократить долгие нагрузки на улице.",
    "плохой": "Лучше сократить пробежки и долгие прогулки, проветривать ненадолго.",
    "очень плохой": "Лучше остаться дома и закрыть окна; на улице — без нагрузок.",
    "крайне плохой": "Лучше остаться дома и закрыть окна; на улице — без нагрузок.",
}
POLLEN_WORDS = ["низкая", "средняя", "высокая", "очень высокая"]


def aqi_level(aqi: float) -> tuple[str, str]:
    for top, emoji, word in AQI_LEVELS:
        if aqi <= top:
            return emoji, word
    return AQI_LEVELS[-1][1:]


def pollen_level(var: str, value: float) -> str | None:
    """Словесная оценка концентрации пыльцы или None, если её почти нет."""
    lo, mid, hi = POLLEN[var][1]
    if value < 1:
        return None
    if value < lo:
        return POLLEN_WORDS[0]
    if value < mid:
        return POLLEN_WORDS[1]
    return POLLEN_WORDS[2] if value < hi else POLLEN_WORDS[3]


def worst_ahead(data: dict, hours: int = 24) -> tuple[float, str] | None:
    """Максимум EAQI в ближайшие часы: (значение, «около ЧЧ:ММ» или «завтра около ЧЧ:ММ»)."""
    h = data.get("hourly") or {}
    times, vals = h.get("time") or [], h.get("european_aqi") or []
    now = (data.get("current") or {}).get("time", "")[:13]
    pairs = [(v, t) for t, v in zip(times, vals) if v is not None and t[:13] >= now][:hours]
    if not pairs:
        return None
    v, t = max(pairs, key=lambda p: p[0])
    when = f"около {t[11:16]}"
    return v, (when if t[:10] == now[:10] else "завтра " + when)


def format_air(name: str, data: dict) -> str:
    cur = data.get("current") or {}
    lines = [f"🌫 <b>Воздух — {name}</b>", ""]
    aqi = cur.get("european_aqi")
    if aqi is None:
        return "\n".join(lines + ["Нет данных о качестве воздуха для этого места 🤷"])
    emoji, word = aqi_level(aqi)
    lines.append(f"{emoji} Качество воздуха: <b>{word}</b> (индекс EAQI {round(aqi)})")
    parts = []
    for key, label in (("pm2_5", "PM2.5"), ("pm10", "PM10"), ("nitrogen_dioxide", "NO₂"), ("ozone", "O₃")):
        if cur.get(key) is not None:
            parts.append(f"{label} {round(cur[key])}")
    if parts:
        lines.append("🔬 " + ", ".join(parts) + " мкг/м³")
    ahead = worst_ahead(data)
    if ahead and aqi_level(ahead[0])[1] != word and ahead[0] > aqi:
        e2, w2 = aqi_level(ahead[0])
        lines.append(f"⏳ В ближайшие сутки ухудшится до «{w2}» {e2} {ahead[1]}")
    tip = AQI_ADVICE.get(word)
    if tip:
        lines.append(f"💡 {tip}")

    lines.append("")
    lines.append(pollen_line(cur))
    return "\n".join(lines)


def pollen_line(cur: dict) -> str:
    """«🌼 Пыльца: берёза — высокая (150)» по current из Open-Meteo Air Quality."""
    pollen = []
    for var, (title, _) in POLLEN.items():
        v = cur.get(var)
        level = pollen_level(var, v) if v is not None else None
        if level:
            pollen.append((POLLEN_WORDS.index(level), f"{title} — {level} ({round(v)})"))
    if pollen:
        pollen.sort(key=lambda p: -p[0])
        return "🌼 Пыльца: " + "; ".join(p[1] for p in pollen)
    if any(cur.get(v) is not None for v in POLLEN):
        return "🌼 Пыльцы в воздухе почти нет"
    return "🌼 Прогноз пыльцы доступен только для Европы"


# ---------- WAQI (aqicn.org): измерения ближайшей станции ----------

WAQI_URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"
WAQI_RADIUS_KM = 5  # станция дальше — значения не показываем
# Индекс US AQI (EPA), который отдаёт WAQI: верхняя граница → оценка
US_AQI_LEVELS = [(50, "🟢", "хороший"), (100, "🟡", "умеренный"), (150, "🟠", "вредный для чувствительных"),
                 (200, "🔴", "вредный"), (300, "🟣", "очень вредный"), (float("inf"), "🟤", "опасный")]
US_AQI_ADVICE = {
    "вредный для чувствительных": AQI_ADVICE["умеренный"],
    "вредный": AQI_ADVICE["плохой"],
    "очень вредный": AQI_ADVICE["очень плохой"],
    "опасный": AQI_ADVICE["крайне плохой"],
}


def us_aqi_level(aqi: float) -> tuple[str, str]:
    for top, emoji, word in US_AQI_LEVELS:
        if aqi <= top:
            return emoji, word
    return US_AQI_LEVELS[-1][1:]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def format_waqi(name: str, data: dict, lat: float, lon: float, pollen: dict | None = None) -> str:
    """data — поле data ответа WAQI feed; pollen — current из Open-Meteo для строки о пыльце (или None)."""
    lines = [f"🌫 <b>Воздух — {name}</b>", ""]
    city = data.get("city") or {}
    station = city.get("name") or "станция без названия"
    geo = city.get("geo") or []
    dist = distance_km(lat, lon, float(geo[0]), float(geo[1])) if len(geo) == 2 else None
    aqi = data.get("aqi")
    if dist is None or dist > WAQI_RADIUS_KM:
        where = f": ближайшая — {station}, {dist:.0f} км" if dist is not None else ""
        lines.append(f"📡 Станций WAQI в пределах {WAQI_RADIUS_KM} км нет{where}. "
                     "Источник можно сменить в /settings.")
    elif not isinstance(aqi, (int, float)):
        lines.append(f"📡 Станция {station} ({dist:.1f} км) сейчас не передаёт данные 🤷")
    else:
        when = ((data.get("time") or {}).get("s") or "")[:16]
        stamp = f", измерено {when[8:10]}.{when[5:7]} {when[11:16]}" if len(when) == 16 else ""
        lines.append(f"📡 Станция: {station}, {dist:.1f} км{stamp}")
        emoji, word = us_aqi_level(aqi)
        lines.append(f"{emoji} Качество воздуха: <b>{word}</b> (индекс US AQI {round(aqi)})")
        iaqi = data.get("iaqi") or {}
        parts = [f"{label} {round(iaqi[k]['v'])}" for k, label in
                 (("pm25", "PM2.5"), ("pm10", "PM10"), ("no2", "NO₂"), ("o3", "O₃"))
                 if isinstance((iaqi.get(k) or {}).get("v"), (int, float))]
        if parts:
            lines.append("🔬 Индексы: " + ", ".join(parts))
        tip = US_AQI_ADVICE.get(word)
        if tip:
            lines.append(f"💡 {tip}")
    if pollen is not None:
        lines += ["", pollen_line(pollen)]
    lines += ["", "<i>Данные: World Air Quality Index Project (aqicn.org)</i>"]
    return "\n".join(lines)
