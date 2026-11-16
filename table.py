"""Текстовая таблица на 3 дня, как в wttr.in: утро / день / вечер / ночь моноширинным шрифтом, без картинок."""
from __future__ import annotations

from datetime import date
from html import escape

from i18n import N_, _, wd
from weather import WMO

# (название, часы): ночь — после полуночи следующих суток, как её обычно и понимают
PERIODS = [(N_("утро"), range(6, 12)), (N_("день"), range(12, 18)), (N_("вечер"), range(18, 24)),
           (N_("ночь"), range(24, 30))]
# Что важнее показать за период: гроза > снег > дождь > туман > облака > ясно
SEVERITY = {95: 9, 96: 9, 99: 9, 75: 8, 86: 8, 73: 7, 85: 7, 71: 6, 77: 6, 65: 6, 82: 6, 67: 6, 57: 6,
            63: 5, 81: 5, 66: 5, 56: 5, 61: 4, 80: 4, 55: 4, 53: 3, 51: 3, 45: 2, 48: 2, 3: 1, 2: 1, 1: 0, 0: 0}


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else str(t)


def period_summary(hourly: dict, day: str, hours: range) -> dict | None:
    """Сводка за часы day+hours (часы ≥ 24 — следующие сутки): температура, осадки, ветер, погода."""
    times = hourly.get("time") or []
    from datetime import timedelta

    d0 = date.fromisoformat(day)
    wanted = {f"{d0 + timedelta(days=h // 24)}T{h % 24:02d}:00" for h in hours}
    idx = [i for i, t in enumerate(times) if t in wanted]

    def vals(key):
        col = hourly.get(key) or []
        return [col[i] for i in idx if i < len(col) and col[i] is not None]

    temps = vals("temperature_2m")
    if not temps:
        return None
    codes = vals("weather_code")
    probs, precs, winds = vals("precipitation_probability"), vals("precipitation"), vals("wind_speed_10m")
    return {"tmin": min(temps), "tmax": max(temps),
            "code": max(codes, key=lambda c: SEVERITY.get(c, 0)) if codes else None,
            "prob": max(probs) if probs else None, "prec": sum(precs) if precs else 0.0,
            "wind": max(winds) if winds else None}


def format_table(name: str, data: dict, days: int = 3) -> str:
    """HTML для Telegram: заголовок и блок <pre> с таблицей. Прошедшие сегодня периоды не показываются."""
    hourly = data.get("hourly") or {}
    now = (data.get("current") or {}).get("time", "")
    day_list = ((data.get("daily") or {}).get("time") or [])[:days]
    out = [_("📋 <b>{name}</b> — на {n} дня по периодам", name=name, n=days), ""]
    rows = []
    for k, day in enumerate(day_list):
        d = date.fromisoformat(day)
        block = []
        for label, hours in PERIODS:
            if k == 0 and now[:10] == day and now[11:13] and hours.stop <= 24 and int(now[11:13]) >= hours.stop:
                continue  # этот период сегодня уже закончился
            s = period_summary(hourly, day, hours)
            if not s:
                continue
            temp = _deg(s["tmin"]) if round(s["tmin"]) == round(s["tmax"]) else f"{_deg(s['tmin'])}…{_deg(s['tmax'])}"
            prob = f"{s['prob']}%" if s["prob"] is not None else (_("дождь") if s["prec"] >= 0.1 else "—")
            wind = f"{round(s['wind'])}" if s["wind"] is not None else "—"
            emoji = WMO.get(s["code"], ("", ""))[1] if s["code"] is not None else ""
            block.append(f"{_(label):<6}{temp + '°':>8} {prob:>5} {wind:>3} {_('м/с')} {emoji}")
        if block:
            title = _("Сегодня") if now[:10] == day else f"{wd(d.weekday())} {d:%d.%m}"
            rows.append(f"{title}\n" + "\n".join(block))
    if not rows:
        return "\n".join(out + [_("Нет почасовых данных 🤷")])
    header = f"{'':<6}{'°C':>8} {'☔':>5} {_('ветер'):>7}"

    out.append("<pre>" + escape(header + "\n" + "\n\n".join(rows)) + "</pre>")
    return "\n".join(out)
