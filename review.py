"""Итоги недели: какая была погода и насколько точным был прогноз на завтра.

Прогноз на завтра бот записывает каждый вечер (ForecastLog) для мест из «Моих мест», рассылок
и предупреждений. Фактическая погода — анализ Open-Meteo за прошедшие дни (модели с учётом наблюдений).
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from i18n import _, wd, wd_lower
from weather import Place

KEEP_DAYS = 35
RAIN_MM = 0.5  # «были осадки» — от 0,5 мм за сутки
GOOD, FAIR = 2, 4  # ошибка прогноза температуры, °C


def key(lat: float, lon: float) -> str:
    return f"{lat:.2f},{lon:.2f}"


class ForecastLog:
    """«широта,долгота» → {"name", "made": дата последней записи, "days": {дата: {tmax, tmin, prec}}}
    плюс "_sent": {user_id: дата последних отправленных итогов недели}. Хранится в JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    def logged_on(self, place: Place) -> str | None:
        """Дата (UTC), когда для места последний раз записывали прогноз."""
        return (self._data.get(key(place.lat, place.lon)) or {}).get("logged")

    def record(self, place: Place, data: dict, logged: str | None = None) -> str | None:
        """Запомнить прогноз на завтра из ответа WeatherClient.fetch (daily начинается с сегодня)."""
        daily = data.get("daily") or {}
        times = daily.get("time") or []
        if len(times) < 2:
            return None

        def at(name):
            col = daily.get(name) or []
            return col[1] if len(col) > 1 else None

        if at("temperature_2m_max") is None or at("temperature_2m_min") is None:
            return None
        entry = self._data.setdefault(key(place.lat, place.lon), {"days": {}})
        entry["name"], entry["made"] = place.name, times[0]
        if logged:
            entry["logged"] = logged
        entry["days"][times[1]] = {"tmax": at("temperature_2m_max"), "tmin": at("temperature_2m_min"),
                                   "prec": at("precipitation_sum") or 0.0}
        cutoff = (date.fromisoformat(times[0]) - timedelta(days=KEEP_DAYS)).isoformat()
        entry["days"] = {d: v for d, v in entry["days"].items() if d >= cutoff}
        self._save()
        return times[1]

    def forecasts(self, place: Place) -> dict[str, dict]:
        return dict((self._data.get(key(place.lat, place.lon)) or {}).get("days") or {})

    def first_day(self) -> str | None:
        days = [d for k, v in self._data.items() if not k.startswith("_") for d in (v.get("days") or {})]
        return min(days, default=None)

    def sent(self, user_id: int) -> str | None:
        return (self._data.get("_sent") or {}).get(str(user_id))

    def mark_sent(self, user_id: int, day: str) -> None:
        self._data.setdefault("_sent", {})[str(user_id)] = day
        self._save()


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else str(t)


def day_mark(err: float, rain_ok: bool) -> str:
    if err <= GOOD and rain_ok:
        return "✅"
    if err <= FAIR:
        return "🟡"
    return "❌"


def format_review(name: str, past: dict, forecasts: dict[str, dict], logging_since: str | None = None) -> str:
    """past — WeatherClient.fetch_past, forecasts — ForecastLog.forecasts для этого места."""
    daily = past.get("daily") or {}
    times = daily.get("time") or []
    tmax, tmin = daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or []
    prec = daily.get("precipitation_sum") or []
    rows = [(date.fromisoformat(t), tmax[i], tmin[i], prec[i] if i < len(prec) else None)
            for i, t in enumerate(times) if i < len(tmax) and i < len(tmin)
            and tmax[i] is not None and tmin[i] is not None]
    if not rows:
        return f"📈 <b>{name}</b>\n" + _("Нет данных о прошедшей неделе 🤷")
    out = [_("📈 <b>{name}</b> — итоги недели {a:%d.%m}–{b:%d.%m}", name=name, a=rows[0][0], b=rows[-1][0]), ""]
    errs_hi, errs_lo, rain_hits, checked = [], [], 0, 0
    for d, hi, lo, p in rows:
        rain = _(", 💧 {mm:.1f} мм", mm=p) if p and p >= RAIN_MM else ""
        line = f"{wd(d.weekday())} {d:%d.%m}: {_deg(lo)}…{_deg(hi)}°{rain}"
        f = forecasts.get(d.isoformat())
        if f:
            e_hi, e_lo = abs(f["tmax"] - hi), abs(f["tmin"] - lo)
            rain_ok = ((f.get("prec") or 0) >= RAIN_MM) == ((p or 0) >= RAIN_MM)
            errs_hi.append(e_hi), errs_lo.append(e_lo)
            rain_hits += rain_ok
            checked += 1
            frain = _(", с осадками") if (f.get("prec") or 0) >= RAIN_MM else ""
            line += _("  {mark} прогноз {lo}…{hi}°{rain}", mark=day_mark(max(e_hi, e_lo), rain_ok),
                      lo=_deg(f['tmin']), hi=_deg(f['tmax']), rain=frain)
        out.append(line)
    mean = sum((hi + lo) / 2 for _, hi, lo, _ in rows) / len(rows)
    warm = max(rows, key=lambda r: r[1])
    cold = min(rows, key=lambda r: r[2])
    total = sum(r[3] or 0 for r in rows)
    wet_days = sum(1 for r in rows if (r[3] or 0) >= RAIN_MM)
    out += ["", _("🌡 Средняя температура {mean:+.1f}°. Теплее всего — {wd1} ({t1}°), холоднее всего — {wd2} ({t2}°)",
                  mean=mean, wd1=wd_lower(warm[0].weekday()), t1=_deg(warm[1]),
                  wd2=wd_lower(cold[0].weekday()), t2=_deg(cold[2]))]
    out.append(_("💧 Осадки: {mm:.1f} мм, {n} дн. из {total}", mm=total, n=wet_days, total=len(rows)) if wet_days
               else _("💧 Неделя без осадков"))
    if checked:
        out += ["", _("🎯 Прогноз на завтра ({n} дн.): ошибка днём в среднем {hi:.1f}°, ночью {lo:.1f}°; "
                      "осадки угаданы в {hits} из {n}", n=checked, hi=sum(errs_hi) / checked,
                      lo=sum(errs_lo) / checked, hits=rain_hits),
                _("✅ ошибка до 2° и осадки угаданы · 🟡 до 4° · ❌ больше 4°")]
    elif logging_since:
        out += ["", _("🎯 Точность прогноза: бот записывает прогнозы с {d:%d.%m}, для этого места записей пока нет. "
                      "Записываются места из ⭐ Моих мест, рассылок и предупреждений.",
                      d=date.fromisoformat(logging_since))]
    else:
        out += ["", _("🎯 Точность прогноза появится через день: бот начал записывать прогнозы на завтра для "
                      "⭐ Моих мест, рассылок и предупреждений.")]
    out.append(_("Фактическая погода — по данным Open-Meteo (модели с учётом наблюдений)."))

    return "\n".join(out)
