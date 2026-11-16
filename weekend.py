"""Прогноз на ближайшие выходные и сравнение «Моих мест»."""
from __future__ import annotations

from datetime import date

from i18n import _
from weather import WMO, describe

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
        return _("⛈ Возможна гроза — планы лучше под крышей")
    if code in SNOW_CODES and prob >= 50:
        return _("🌨 Снежно — тёплая обувь и запас времени на дорогу")
    if prob >= 60 or code in RAIN_CODES and prob >= 40:
        return _("☔️ Скорее дождливо — зонт обязателен")
    if (wind or 0) >= 10:
        return _("💨 Ветрено — для прогулок не лучший день")
    if code in SNOW_CODES:  # снег по прогнозу, но вероятность невысокая — «сухо» было бы неправдой
        return _("🌨 Возможен небольшой снег — одевайтесь теплее")
    if code in RAIN_CODES:
        return _("🤔 Переменчиво — возьмите зонт на всякий случай")
    if prob <= 30 and tmax is not None and tmax >= 15:
        return _("😎 Отличный день для прогулки или поездки")
    if prob <= 30:
        return _("👍 Сухо — можно гулять, одевайтесь по погоде")
    return _("🤔 Переменчиво — возьмите зонт на всякий случай")


def format_weekend(name: str, data: dict) -> str:
    d = data.get("daily") or {}
    times = d.get("time") or []
    now = (data.get("current") or {}).get("time", "")  # местное время места
    today = now[:10] or date.today().isoformat()
    late = len(now) >= 13 and int(now[11:13]) >= EVENING
    idx = weekend_indices(times)
    lines = [_("🏖 <b>Выходные — {name}</b>", name=name), ""]
    if late and idx and times[idx[0]] == today:  # вечером сегодняшний день почти прошёл
        idx = idx[1:] or weekend_indices(times, idx[0] + 1)
        lines += [_("🌙 Сегодня уже вечер — показываю завтра.") if len(idx) == 1 and idx[0] == 1
                  else _("🌙 Сегодня уже вечер — показываю следующие выходные."), ""]
    if not idx:
        return "\n".join(lines + [_("Нет прогноза на выходные 🤷")])

    def col(key, i):
        v = d.get(key)
        return v[i] if v and i < len(v) else None

    for i in idx:
        day = date.fromisoformat(d["time"][i])
        code, hi, lo = col("weather_code", i), col("temperature_2m_max", i), col("temperature_2m_min", i)
        prob, rain, wind = col("precipitation_probability_max", i), col("precipitation_sum", i), \
            col("wind_speed_10m_max", i)
        title = _("сегодня") if d["time"][i] == today else f"{day:%d.%m}"
        lines.append(f"<b>{[_('Суббота'), _('Воскресенье')][day.weekday() - 5]}, {title}</b>")
        if code is not None:
            lines.append(describe(code))
        if hi is not None and lo is not None:
            lines.append(f"🌡 {_deg(lo)}…{_deg(hi)}°C")
        if prob is not None or rain:
            line = _("☔️ Вероятность осадков {p}%", p=prob or 0)
            if rain:
                line += _(", {mm:.1f} мм", mm=rain)
            lines.append(line)
        if wind is not None:
            lines.append(_("💨 Ветер до {w} м/с", w=round(wind)))
        lines.append(verdict(code, prob, wind, hi))
        lines.append("")
    if len(idx) == 2:
        p = [col("precipitation_probability_max", i) or 0 for i in idx]
        if abs(p[0] - p[1]) >= 30:
            lines.append(_("👉 Для дел на улице лучше суббота") if p[0] < p[1]
                         else _("👉 Для дел на улице лучше воскресенье"))
    return "\n".join(lines).rstrip()


def compare_text(rows: list[tuple[str, dict | None]]) -> str:
    """rows: [(название, данные fetch или None при ошибке)] → сводка «Моих мест»."""
    lines = [_("📊 <b>Сравнение моих мест</b>"), ""]
    now = []
    for name, data in rows:
        if not data:
            lines.append(_("📍 <b>{name}</b>: нет данных 🙏", name=name))
            continue
        cur, d = data.get("current") or {}, data.get("daily") or {}
        code = cur.get("weather_code")
        emoji = WMO.get(code, ("", "🌡"))[1]
        line = f"📍 <b>{name}</b>: {emoji} {_deg(cur['temperature_2m'])}°"
        if cur.get("apparent_temperature") is not None:
            line += _(" (ощущ. {t}°)", t=_deg(cur['apparent_temperature']))
        try:
            line += "\n    " + _("сегодня {lo}…{hi}°, ☔️ {p}%", lo=_deg(d['temperature_2m_min'][0]),
                                 hi=_deg(d['temperature_2m_max'][0]), p=d['precipitation_probability_max'][0] or 0)
        except (KeyError, IndexError, TypeError):
            pass
        if cur.get("wind_speed_10m") is not None:
            line += _(", 💨 {w} м/с", w=round(cur['wind_speed_10m']))
        lines.append(line)
        now.append((cur["temperature_2m"], name))
    if len(now) >= 2:
        warm, cold = max(now), min(now)
        if round(warm[0]) != round(cold[0]):
            lines += ["", _("🔥 Теплее всего сейчас: {name} ({t}°)", name=warm[1], t=_deg(warm[0])),
                      _("❄️ Холоднее всего: {name} ({t}°)", name=cold[1], t=_deg(cold[0]))]

    return "\n".join(lines)
