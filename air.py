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
    """Максимум EAQI в ближайшие часы: (значение, время ЧЧ:ММ)."""
    h = data.get("hourly") or {}
    times, vals = h.get("time") or [], h.get("european_aqi") or []
    now = (data.get("current") or {}).get("time", "")[:13]
    pairs = [(v, t) for t, v in zip(times, vals) if v is not None and t[:13] >= now][:hours]
    if not pairs:
        return None
    v, t = max(pairs, key=lambda p: p[0])
    return v, t[11:16]


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
        lines.append(f"⏳ В ближайшие сутки ухудшится до «{w2}» {e2} около {ahead[1]}")
    tip = AQI_ADVICE.get(word)
    if tip:
        lines.append(f"💡 {tip}")

    pollen = []
    for var, (title, _) in POLLEN.items():
        v = cur.get(var)
        level = pollen_level(var, v) if v is not None else None
        if level:
            pollen.append((POLLEN_WORDS.index(level), f"{title} — {level} ({round(v)})"))
    lines.append("")
    if pollen:
        pollen.sort(key=lambda p: -p[0])
        lines.append("🌼 Пыльца: " + "; ".join(p[1] for p in pollen))
    elif any(cur.get(v) is not None for v in POLLEN):
        lines.append("🌼 Пыльцы в воздухе почти нет")
    else:
        lines.append("🌼 Прогноз пыльцы доступен только для Европы")
    return "\n".join(lines)
