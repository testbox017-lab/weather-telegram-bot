"""Радар осадков: последний кадр RainViewer поверх карты OpenStreetMap и прогноз осадков
Open-Meteo с шагом 15 минут на ближайшие часы.

RainViewer (бесплатный API) отдаёт снимки радаров за последние ~2 часа, тайлы до 7-го масштаба.
Тайлы карты OSM берём с понятным User-Agent и держим в памяти: так требует политика tile.openstreetmap.org.
"""
from __future__ import annotations

import asyncio
import io
import logging
import math
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import aiohttp
from PIL import Image, ImageDraw

from weather import NOMINATIM_UA

MAPS_URL = "https://api.rainviewer.com/public/weather-maps.json"
OSM_TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
RADAR_TILE = "{host}{path}/256/{z}/{x}/{y}/2/1_1.png"  # схема 2 (Universal Blue), сглаживание, снег отдельно
ZOOM = 7  # больше бесплатный RainViewer не отдаёт; ~0,8 км на пиксель на широте Украины
SIZE = 640  # сторона картинки, px (около 500 км)
RING_KM = 50
TILE = 256
HEADERS = {"User-Agent": NOMINATIM_UA}
WET_MM = 0.1  # мм за 15 минут — уже осадки


class TileCache:
    """Небольшой LRU-кэш тайлов в памяти: url → PNG (None — тайла нет)."""

    def __init__(self, size: int):
        self.size, self._data = size, OrderedDict()

    def get(self, url: str):
        if url in self._data:
            self._data.move_to_end(url)
            return self._data[url]
        return ...

    def put(self, url: str, value) -> None:
        self._data[url] = value
        self._data.move_to_end(url)
        while len(self._data) > self.size:
            self._data.popitem(last=False)


base_tiles = TileCache(256)  # карта не меняется
radar_tiles = TileCache(128)  # кадры радара — каждые 10 минут новые, url у них свой


def tile_xy(lat: float, lon: float, z: int = ZOOM) -> tuple[float, float]:
    """Координаты точки в тайлах (дробные) в проекции Web Mercator."""
    n = 2 ** z
    lat = max(min(lat, 85.0), -85.0)
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def km_per_px(lat: float, z: int = ZOOM) -> float:
    return 40075.016686 * math.cos(math.radians(lat)) / (TILE * 2 ** z)


def latest_frame(maps: dict) -> tuple[str, int, str] | None:
    """(host, время UTC в секундах, path) последнего кадра; прогнозные кадры (nowcast), если есть, — новее."""
    radar = maps.get("radar") or {}
    frames = [f for f in (radar.get("past") or []) + (radar.get("nowcast") or [])
              if isinstance(f, dict) and f.get("path") and f.get("time")]
    past = [f for f in radar.get("past") or [] if isinstance(f, dict) and f.get("path") and f.get("time")]
    pick = max(past or frames, key=lambda f: f["time"], default=None)
    if not pick or not maps.get("host"):
        return None
    return maps["host"], int(pick["time"]), pick["path"]


async def _fetch_png(session: aiohttp.ClientSession, url: str, cache: TileCache) -> bytes | None:
    hit = cache.get(url)
    if hit is not ...:
        return hit
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as r:
            body = await r.read() if r.status == 200 else None
            if r.status not in (200, 404):  # временная ошибка — не запоминаем
                logging.warning("tile %s: HTTP %s", url, r.status)
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError):
        logging.warning("tile %s: нет связи", url)
        return None
    cache.put(url, body)
    return body


def _open(png: bytes | None) -> Image.Image | None:
    if not png:
        return None
    try:
        return Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:
        return None


def compose(lat: float, lon: float, tiles: dict[tuple[int, int], tuple[bytes | None, bytes | None]],
            z: int = ZOOM, size: int = SIZE) -> bytes:
    """PNG: карта, поверх радар, в центре — точка места и круг RING_KM. tiles: (x, y) → (карта, радар)."""
    fx, fy = tile_xy(lat, lon, z)
    left, top = fx * TILE - size / 2, fy * TILE - size / 2
    canvas = Image.new("RGBA", (size, size), (238, 238, 238, 255))
    radar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for (tx, ty), (base_png, radar_png) in tiles.items():
        pos = (round(tx * TILE - left), round(ty * TILE - top))
        if (img := _open(base_png)) is not None:
            canvas.paste(img, pos)
        if (img := _open(radar_png)) is not None:
            radar.paste(img, pos)
    canvas = Image.blend(canvas, Image.new("RGBA", canvas.size, (255, 255, 255, 255)), 0.25)  # карта бледнее
    radar.putalpha(radar.getchannel("A").point(lambda a: a * 85 // 100))
    canvas = Image.alpha_composite(canvas, radar)
    d = ImageDraw.Draw(canvas)
    c, r = size / 2, RING_KM / km_per_px(lat, z)
    d.ellipse((c - r, c - r, c + r, c + r), outline=(73, 80, 87, 200), width=2)
    d.ellipse((c - 6, c - 6, c + 6, c + 6), fill=(224, 49, 49, 255), outline=(255, 255, 255, 255), width=2)
    note = "(c) OpenStreetMap contributors, RainViewer"
    w = d.textlength(note)
    d.rectangle((size - w - 8, size - 16, size, size), fill=(255, 255, 255, 200))
    d.text((size - w - 4, size - 14), note, fill=(73, 80, 87, 255))
    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def needed_tiles(lat: float, lon: float, z: int = ZOOM, size: int = SIZE) -> list[tuple[int, int]]:
    fx, fy = tile_xy(lat, lon, z)
    n = 2 ** z
    x0, x1 = math.floor(fx - size / 2 / TILE), math.floor(fx + size / 2 / TILE)
    y0, y1 = math.floor(fy - size / 2 / TILE), math.floor(fy + size / 2 / TILE)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(max(y0, 0), min(y1, n - 1) + 1)]


async def radar_image(session: aiohttp.ClientSession, lat: float, lon: float) -> tuple[bytes, datetime]:
    """Картинка радара и время кадра (UTC). Нет кадров у RainViewer — ValueError."""
    async with session.get(MAPS_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
        r.raise_for_status()
        maps = await r.json()
    frame = latest_frame(maps)
    if not frame:
        raise ValueError("RainViewer не прислал кадров")
    host, ts, path = frame
    n = 2 ** ZOOM
    coords = needed_tiles(lat, lon)

    async def pair(x: int, y: int):
        xx = x % n  # через 180-й меридиан
        return await asyncio.gather(
            _fetch_png(session, OSM_TILE.format(z=ZOOM, x=xx, y=y), base_tiles),
            _fetch_png(session, RADAR_TILE.format(host=host, path=path, z=ZOOM, x=xx, y=y), radar_tiles))

    got = await asyncio.gather(*(pair(x, y) for x, y in coords))
    tiles = {xy: tuple(v) for xy, v in zip(coords, got)}
    return compose(lat, lon, tiles), datetime.fromtimestamp(ts, timezone.utc)


def nowcast_text(data: dict, hours: int = 3) -> str:
    """Осадки на ближайшие hours часов по 15-минутному прогнозу Open-Meteo."""
    m = data.get("minutely_15") or {}
    times, prec, snow = m.get("time") or [], m.get("precipitation") or [], m.get("snowfall") or []
    now = (data.get("current") or {}).get("time")
    if not times or not now:
        return "Прогноза осадков по 15 минут для этого места нет 🤷"
    start = datetime.fromisoformat(now)
    end = start + timedelta(hours=hours)
    slots = [(datetime.fromisoformat(t), prec[i] or 0, (snow[i] or 0) if i < len(snow) else 0)
             for i, t in enumerate(times) if i < len(prec)
             and start - timedelta(minutes=14) <= datetime.fromisoformat(t) < end]
    if not slots:
        return "Прогноза осадков по 15 минут для этого места нет 🤷"
    wet = [s for s in slots if s[1] >= WET_MM]
    if not wet:
        return f"☀️ В ближайшие {hours} ч осадков не ожидается"
    kind = "снег" if sum(s[2] for s in wet) > 0 else "дождь"
    icon = "🌨" if kind == "снег" else "🌧"
    peak = max(s[1] for s in wet)
    first, last = wet[0][0], wet[-1][0] + timedelta(minutes=15)
    raining_now = slots[0][1] >= WET_MM
    if raining_now:
        stop = next((s[0] for s in slots if s[1] < WET_MM), None)
        when = f"Сейчас идёт {kind}" + (f", закончится около {stop:%H:%M}" if stop else
                                         f" и не закончится в ближайшие {hours} ч")
    else:
        when = f"{kind.capitalize()} начнётся около {first:%H:%M}" + (
            f", продлится до ~{last:%H:%M}" if last < end else "")
    return f"{icon} {when}, до {peak:.1f} мм за 15 минут"
