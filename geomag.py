"""Магнитные бури: планетарный индекс Kp от NOAA SWPC (бесплатно, без ключа).

Прогноз на 3 суток с шагом 3 часа. Kp от 5 — буря (G1), 6 — G2, 7 — G3, 8 — G4, 9 — G5;
4 — поле возмущено. Ответ NOAA общий для всех мест, поэтому держим его в памяти CACHE_FOR.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from i18n import _

URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
CACHE_FOR = 1800
STORM_KP = 4.67     # «5−» по шкале NOAA — уже G1
ACTIVE_KP = 4.0
_cache: tuple[float, list] | None = None


def parse(raw) -> list[tuple[datetime, float, str]]:
    """[(время UTC, Kp, observed/estimated/predicted)]. Понимает и список объектов, и старый формат
    «список списков с заголовком»."""
    rows = []
    for item in raw or []:
        if isinstance(item, dict):
            t, kp, kind = item.get("time_tag"), item.get("kp"), item.get("observed") or ""
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            t, kp, kind = item[0], item[1], item[2] or ""
        else:
            continue
        try:
            when = datetime.fromisoformat(str(t).replace("Z", "")).replace(tzinfo=timezone.utc)
            rows.append((when, float(kp), str(kind)))
        except (TypeError, ValueError):
            continue  # заголовок или битая строка
    return sorted(rows)


async def fetch(session, now: float | None = None) -> list[tuple[datetime, float, str]]:
    global _cache
    now = time.time() if now is None else now
    if _cache and now - _cache[0] < CACHE_FOR:
        return _cache[1]
    import aiohttp

    async with session.get(URL, timeout=aiohttp.ClientTimeout(total=10)) as r:
        r.raise_for_status()
        rows = parse(await r.json(content_type=None))
    if rows:
        _cache = (now, rows)
    return rows


async def safe_fetch(session) -> list | None:
    """То же, но при ошибке — None (строка про бури просто не покажется)."""
    try:
        return await fetch(session)
    except Exception as e:  # noqa: BLE001
        logging.warning("NOAA Kp недоступен: %r", e)
        return None


def level(kp: float) -> str | None:
    """G1…G5 или None, если не буря."""
    if kp < STORM_KP:
        return None
    return f"G{min(5, max(1, round(kp) - 4))}"


def outlook(rows: list | None, now: datetime, offset: int = 0, hours: int = 24) -> dict | None:
    """Максимум Kp от текущего 3-часового интервала на hours вперёд: {kp, at (местное время), day, level}."""
    if not rows:
        return None
    start = now - timedelta(hours=3)
    window = [r for r in rows if start < r[0] <= now + timedelta(hours=hours)]
    if not window:
        return None
    when, kp, _kind = max(window, key=lambda r: r[1])
    local = when + timedelta(seconds=offset)
    return {"kp": kp, "at": local.strftime("%H:%M"), "day": local.date().isoformat(), "level": level(kp)}


def text(o: dict | None) -> str | None:
    if not o:
        return None
    kp = round(o["kp"])
    if o["level"]:
        return _("🧲 Магнитная буря {g} (Kp {kp}) около {at}", g=o["level"], kp=kp, at=o["at"])
    if o["kp"] >= ACTIVE_KP:
        return _("🧲 Магнитное поле возмущено (Kp до {kp}) около {at}", kp=kp, at=o["at"])
    return _("🧲 Магнитная обстановка спокойная (Kp до {kp})", kp=kp)


def short(o: dict | None) -> str | None:
    if not o:
        return None
    return f"🧲 Kp {round(o['kp'])}" + (f" {o['level']}" if o["level"] else "")


def for_data(rows: list | None, data: dict, now: datetime | None = None) -> dict | None:
    """outlook для места из ответа Open-Meteo (смещение местного времени — utc_offset_seconds)."""
    return outlook(rows, now or datetime.now(timezone.utc), int(data.get("utc_offset_seconds") or 0))
