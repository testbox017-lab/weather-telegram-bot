"""Прогноз на ближайшие выходные и сравнение «Моих мест»."""
from __future__ import annotations

from datetime import date

from weather import DAYS_RU, WMO, describe

RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75, 77, 85, 86}


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else ("−" + str(-t) if t < 0 else "0")


EVENING = 18  # с этого часа сегодняшний день выходных уже не показываем


def weekend_indices(days: list[str], start: int = 0) -> list[int]:
    """Индексы ближайших субботы и воскресенья начиная с days[start] (в воскресенье — только сегодня)."""
    out = []
    for i, d in enumerate(days):
        if i < start:
            continue
        wd = date.fromisoformat(d).weekday()
        if wd in (5, 6):
            out.append(i)
        elif out:
            break
    return out


def verdict(code: int | None, prob: int | None, wind: float | None, tmax: float | None) -> str:
    prob = prob or 0
    if code in {95, 96, 99}:
        return "⛈ Возможна гроза — планы лучше под крышей"
    if code in SNOW_CODES and prob >= 50:
        return "🌨 Снежно — тёплая обувь и запас времени на дорогу"
    if prob >= 60 or code in RAIN_CODES and prob >= 40:
        return "☔️ Скорее дождливо — зонт обязателен"
    if (wind or 0) >= 10:
        return "💨 Ветрено — для прогулок не лучший день"
    if prob <= 30 and tmax is not None and tmax >= 15:
        return "😎 Отличный день для прогулки или поездки"
    if prob <= 30:
        return "👍 Сухо — можно гулять, одевайтесь по погоде"
    return "🤔 Переменчиво — возьмите зонт на всякий случай"


def format_weekend(name: str, data: dict) -> str:
    d = data.get("daily") or {}
    times = d.get("time") or []
    now = (data.get("current") or {}).get("time", "")  # местное время места
    today = now[:10] or date.today().isoformat()
    late = len(now) >= 13 and int(now[11:13]) >= EVENING
    idx = weekend_indices(times)
    lines = [f"🏖 <b>Выходные — {name}</b>", ""]
    if late and idx and times[idx[0]] == today:  # вечером сегодняшний день почти прошёл
        idx = idx[1:] or weekend_indices(times, idx[0] + 1)
        lines += ["🌙 Сегодня уже вечер — показываю " + ("завтра." if len(idx) == 1 and idx[0] == 1
                                                        else "следующие выходные."), ""]
    if not idx:
        return "\n".join(lines + ["Нет прогноза на выходные 🤷"])

    def col(key, i):
        v = d.get(key)
        return v[i] if v and i < len(v) else None

    for i in idx:
        day = date.fromisoformat(d["time"][i])
        code, hi, lo = col("weather_code", i), col("temperature_2m_max", i), col("temperature_2m_min", i)
        prob, rain, wind = col("precipitation_probability_max", i), col("precipitation_sum", i), \
            col("wind_speed_10m_max", i)
        title = "сегодня" if d["time"][i] == today else f"{day:%d.%m}"
        lines.append(f"<b>{['Суббота', 'Воскресенье'][day.weekday() - 5]}, {title}</b>")
        if code is not None:
            lines.append(describe(code))
        if hi is not None and lo is not None:
            lines.append(f"🌡 {_deg(lo)}…{_deg(hi)}°C")
        if prob is not None or rain:
            line = f"☔️ Вероятность осадков {prob or 0}%"
            if rain:
                line += f", {rain:.1f} мм"
            lines.append(line)
        if wind is not None:
            lines.append(f"💨 Ветер до {round(wind)} м/с")
        lines.append(verdict(code, prob, wind, hi))
        lines.append("")
    if len(idx) == 2:
        p = [col("precipitation_probability_max", i) or 0 for i in idx]
        if abs(p[0] - p[1]) >= 30:
            better = "суббота" if p[0] < p[1] else "воскресенье"
            lines.append(f"👉 Для дел на улице лучше {better}")
    return "\n".join(lines).rstrip()


def compare_text(rows: list[tuple[str, dict | None]]) -> str:
    """rows: [(название, данные fetch или None при ошибке)] → сводка «Моих мест»."""
    lines = ["📊 <b>Сравнение моих мест</b>", ""]
    now = []
    for name, data in rows:
        if not data:
            lines.append(f"📍 <b>{name}</b>: нет данных 🙏")
            continue
        cur, d = data.get("current") or {}, data.get("daily") or {}
        code = cur.get("weather_code")
        emoji = WMO.get(code, ("", "🌡"))[1]
        line = f"📍 <b>{name}</b>: {emoji} {_deg(cur['temperature_2m'])}°"
        if cur.get("apparent_temperature") is not None:
            line += f" (ощущ. {_deg(cur['apparent_temperature'])}°)"
        try:
            line += (f"\n    сегодня {_deg(d['temperature_2m_min'][0])}…{_deg(d['temperature_2m_max'][0])}°, "
                     f"☔️ {d['precipitation_probability_max'][0] or 0}%")
        except (KeyError, IndexError, TypeError):
            pass
        if cur.get("wind_speed_10m") is not None:
            line += f", 💨 {round(cur['wind_speed_10m'])} м/с"
        lines.append(line)
        now.append((cur["temperature_2m"], name))
    if len(now) >= 2:
        warm, cold = max(now), min(now)
        if round(warm[0]) != round(cold[0]):
            lines += ["", f"🔥 Теплее всего сейчас: {warm[1]} ({_deg(warm[0])}°)",
                      f"❄️ Холоднее всего: {cold[1]} ({_deg(cold[0])}°)"]
    return "\n".join(lines)
