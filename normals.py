"""Климатическая норма «как обычно в этот день»: средние за 1991–2020 из архива Open-Meteo.

Архив за 30 лет — тяжёлый запрос, поэтому нормы считаются один раз на место (сетка 0.1°)
и хранятся в JSON-файле: на каждый день года средние макс./мин. температуры и доля дней
с осадками, по окну ±3 дня.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from i18n import _

FROM_YEAR, TO_YEAR = 1991, 2020
WINDOW = 3          # ± дней вокруг даты
WET_MM = 1.0        # день с осадками


def place_key(lat: float, lon: float) -> str:
    return f"{round(lat, 1)},{round(lon, 1)}"


def day_key(d: date) -> str:
    return f"{d:%m-%d}"


def compute(daily: dict) -> dict[str, list]:
    """Суточный архив → {"ММ-ДД": [норма макс., норма мин., % дней с осадками]}."""
    by_day: dict[str, list[tuple]] = {}
    times = daily.get("time") or []
    tmax, tmin = daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or []
    prec = daily.get("precipitation_sum") or [None] * len(times)
    for t, hi, lo, p in zip(times, tmax, tmin, prec):
        if hi is None or lo is None:
            continue
        by_day.setdefault(t[5:10], []).append((hi, lo, p))
    out = {}
    ref = date(2000, 1, 1)  # високосный год: есть и 29 февраля
    for i in range(366):
        d = ref + timedelta(days=i)
        rows = []
        for k in range(-WINDOW, WINDOW + 1):
            rows += by_day.get(day_key(d + timedelta(days=k)), [])
        if not rows:
            continue
        wet = [p for _, _, p in rows if p is not None]
        out[day_key(d)] = [round(sum(r[0] for r in rows) / len(rows), 1),
                           round(sum(r[1] for r in rows) / len(rows), 1),
                           round(100 * sum(p >= WET_MM for p in wet) / len(wet)) if wet else None]
    return out


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else ("−" + str(-t) if t < 0 else "0")


def norm_text(norm: dict | None, day: date, tmax: float | None = None, tmin: float | None = None) -> str | None:
    """«📈 Обычно 14.11: днём +7°, ночью +1° — сегодня на 3° теплее нормы»."""
    row = (norm or {}).get(day_key(day))
    if not row:
        return None
    hi, lo, wet = row
    text = _("📈 Обычно {d:%d.%m}: днём {hi}°, ночью {lo}°", d=day, hi=_deg(hi), lo=_deg(lo))
    if wet is not None:
        text += _(", осадки в {p}% лет", p=wet)
    if tmax is not None and tmin is not None:
        diff = round((tmax + tmin) / 2 - (hi + lo) / 2)
        today = day == date.today()
        if diff >= 2:
            text += (_(" — сегодня на {n}° теплее нормы", n=diff) if today
                     else _(" — в этот день на {n}° теплее нормы", n=diff))
        elif diff <= -2:
            text += (_(" — сегодня на {n}° холоднее нормы", n=-diff) if today
                     else _(" — в этот день на {n}° холоднее нормы", n=-diff))
        else:
            text += _(" — около нормы")

    return text


class Normals:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {k: v for k, v in raw.items() if isinstance(v, dict)}
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def cached(self, lat: float, lon: float) -> dict | None:
        return self._data.get(place_key(lat, lon))

    def put(self, lat: float, lon: float, norm: dict) -> None:
        self._data[place_key(lat, lon)] = norm
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, separators=(",", ":")), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    async def load(self, client, lat: float, lon: float) -> dict | None:
        """Норма из кэша или из архива (client.fetch_climate)."""
        norm = self.cached(lat, lon)
        if norm is None:
            daily = await client.fetch_climate(round(lat, 1), round(lon, 1), FROM_YEAR, TO_YEAR)
            norm = compute(daily)
            if norm:
                self.put(lat, lon, norm)
        return norm
