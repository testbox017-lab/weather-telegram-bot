from datetime import datetime, timezone

import pytest

import geomag
from geomag import level, outlook, parse, short, text

NOW = datetime(2026, 11, 27, 13, 0, tzinfo=timezone.utc)
RAW = [  # формат NOAA (список объектов)
    {"time_tag": "2026-11-27T09:00:00", "kp": 3.33, "observed": "observed", "noaa_scale": None},
    {"time_tag": "2026-11-27T12:00:00", "kp": 2.0, "observed": "estimated", "noaa_scale": None},
    {"time_tag": "2026-11-27T15:00:00", "kp": 5.0, "observed": "predicted", "noaa_scale": "G1"},
    {"time_tag": "2026-11-28T21:00:00", "kp": 7.0, "observed": "predicted", "noaa_scale": "G3"},
]


def test_parse_both_formats():
    rows = parse(RAW)
    assert rows[0] == (datetime(2026, 11, 27, 9, tzinfo=timezone.utc), 3.33, "observed") and len(rows) == 4
    old = [["time_tag", "kp", "observed", "noaa_scale"], ["2026-11-27 12:00:00", "2.00", "estimated", None]]
    assert parse(old) == [(datetime(2026, 11, 27, 12, tzinfo=timezone.utc), 2.0, "estimated")]
    assert parse(None) == [] and parse([{"kp": "x"}]) == []


def test_levels():
    assert level(4.33) is None and level(4.67) == "G1" and level(5.67) == "G2" and level(9) == "G5"


def test_outlook_and_texts():
    o = outlook(parse(RAW), NOW, offset=7200)  # Киев зимой
    assert o == {"kp": 5.0, "at": "17:00", "day": "2026-11-27", "level": "G1"}
    assert text(o) == "🧲 Магнитная буря G1 (Kp 5) около 17:00" and short(o) == "🧲 Kp 5 G1"
    calm = outlook(parse(RAW[:2]), NOW)
    assert text(calm) == "🧲 Магнитная обстановка спокойная (Kp до 2)" and short(calm) == "🧲 Kp 2"
    assert text({"kp": 4.0, "at": "18:00", "day": "", "level": None}).startswith("🧲 Магнитное поле возмущено")
    assert outlook([], NOW) is None and text(None) is None


class Resp:
    def __init__(self, data):
        self.data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    async def json(self, content_type=None):
        return self.data


class Session:
    def __init__(self):
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return Resp(RAW)


@pytest.mark.asyncio
async def test_fetch_is_cached(monkeypatch):
    monkeypatch.setattr(geomag, "_cache", None)
    s = Session()
    assert len(await geomag.fetch(s, now=1000)) == 4
    await geomag.fetch(s, now=1000 + geomag.CACHE_FOR - 1)
    assert s.calls == 1
    await geomag.fetch(s, now=1000 + geomag.CACHE_FOR + 1)
    assert s.calls == 2


@pytest.mark.asyncio
async def test_safe_fetch_never_raises(monkeypatch):
    monkeypatch.setattr(geomag, "_cache", None)

    class Broken:
        def get(self, *a, **kw):
            raise OSError("нет сети")

    assert await geomag.safe_fetch(Broken()) is None
