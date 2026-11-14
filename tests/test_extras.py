import asyncio
from datetime import date, timedelta

import air
import normals
import weekend
from charts import compare_chart


def air_data(**cur):
    base = {"time": "2026-11-14T12:00", "european_aqi": 15, "pm2_5": 4.2, "pm10": 9.8,
            "nitrogen_dioxide": 7, "ozone": 50}
    base.update(cur)
    return {"current": base, "hourly": {"time": ["2026-11-14T12:00", "2026-11-14T18:00"],
                                        "european_aqi": [15, base["european_aqi"]]}}


def test_aqi_levels():
    assert air.aqi_level(10)[1] == "хороший"
    assert air.aqi_level(55)[1] == "умеренный"
    assert air.aqi_level(250)[1] == "крайне плохой"


def test_format_air_good_no_pollen_outside_europe():
    text = air.format_air("Бахмач", air_data())
    assert "хороший" in text and "PM2.5 4" in text
    assert "только для Европы" in text
    assert "💡" not in text


def test_format_air_pollen_and_worse_ahead():
    d = air_data(european_aqi=30, birch_pollen=150, grass_pollen=2, ragweed_pollen=0.2)
    d["hourly"]["european_aqi"] = [30, 70]
    text = air.format_air("Киев", d)
    assert "берёза — высокая" in text and "злаки — низкая" in text
    assert "амброзия" not in text
    assert "ухудшится до «плохой»" in text and "18:00" in text


def test_format_air_no_data():
    assert "Нет данных" in air.format_air("X", {"current": {}})


def archive(years=(1991, 1992)):
    times, hi, lo, pr = [], [], [], []
    for y in years:
        d = date(y, 1, 1)
        while d.year == y:
            times.append(d.isoformat())
            hi.append(10.0 if d.month == 11 else 20.0)
            lo.append(2.0 if d.month == 11 else 12.0)
            pr.append(3.0 if d.day % 2 else 0.0)
            d += timedelta(days=1)
    return {"time": times, "temperature_2m_max": hi, "temperature_2m_min": lo, "precipitation_sum": pr}


def test_compute_normals():
    n = normals.compute(archive())
    assert n["11-14"][:2] == [10.0, 2.0]
    assert 40 <= n["11-14"][2] <= 60
    assert "02-29" in n and len(n) == 366


def test_norm_text_warmer_and_near():
    n = {"11-14": [7.0, 1.0, 40]}
    t = normals.norm_text(n, date(2026, 11, 14), 12, 6)
    assert "днём +7°, ночью +1°" in t and "на 5° теплее нормы" in t
    assert "около нормы" in normals.norm_text(n, date(2026, 11, 14), 8, 1)
    assert normals.norm_text(n, date(2026, 11, 15)) is None


def test_normals_cache(tmp_path):
    calls = []

    class Fake:
        async def fetch_climate(self, lat, lon, a, b):
            calls.append((lat, lon))
            return archive()

    store = normals.Normals(tmp_path / "n.json")
    n = asyncio.run(store.load(Fake(), 51.183, 32.833))
    assert n["11-14"][0] == 10.0
    again = normals.Normals(tmp_path / "n.json")
    assert again.cached(51.18, 32.83) is not None  # тот же квадрат 0.1°
    asyncio.run(again.load(Fake(), 51.2, 32.8))
    assert calls == [(51.2, 32.8)]


def week(start: date):
    days = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    return {"daily": {"time": days, "weather_code": [3, 3, 3, 3, 3, 61, 0],
                      "temperature_2m_max": [5] * 5 + [6, 16], "temperature_2m_min": [0] * 7,
                      "precipitation_probability_max": [10] * 5 + [80, 5],
                      "precipitation_sum": [0] * 5 + [4.5, 0], "wind_speed_10m_max": [3] * 7}}


def test_weekend_indices():
    assert weekend.weekend_indices(week(date(2026, 11, 9))["daily"]["time"]) == [5, 6]   # понедельник
    assert weekend.weekend_indices(week(date(2026, 11, 15))["daily"]["time"]) == [0]     # воскресенье


def test_format_weekend():
    text = weekend.format_weekend("Бахмач", week(date(2026, 11, 2)))
    assert "Суббота, 07.11" in text and "Воскресенье, 08.11" in text
    assert "зонт обязателен" in text and "Отличный день" in text
    assert "лучше воскресенье" in text


def test_verdict_storm_and_wind():
    assert "гроза" in weekend.verdict(95, 50, 3, 20)
    assert "Ветрено" in weekend.verdict(0, 0, 12, 20)


def now_data(t):
    return {"current": {"temperature_2m": t, "apparent_temperature": t - 2, "weather_code": 0,
                        "wind_speed_10m": 3},
            "daily": {"temperature_2m_min": [t - 3], "temperature_2m_max": [t + 2],
                      "precipitation_probability_max": [20]}}


def test_compare_text():
    text = weekend.compare_text([("Бахмач", now_data(3)), ("Киев", now_data(7)), ("Сочи", None)])
    assert "Теплее всего сейчас: Киев" in text and "Холоднее всего: Бахмач" in text
    assert "Сочи</b>: нет данных" in text


def test_compare_chart_png():
    days = [(date(2026, 11, 14) + timedelta(days=i)).isoformat() for i in range(7)]
    png = compare_chart([("A", days, [5] * 7, [0] * 7), ("B", days, [8] * 7, [None] * 7)])
    assert png[:4] == b"\x89PNG"


def test_bot_norm_line_and_compare(tmp_path, monkeypatch):
    import core
    from handlers import places as places_router
    from weather import Place

    class Fake:
        async def fetch_climate(self, lat, lon, a, b):
            return archive()

        async def fetch(self, place, days):
            return now_data(5 if place.name == "A" else 9) | {"daily": week(date(2026, 11, 9))["daily"]}

    class Msg:
        def __init__(self):
            self.sent = []

        async def answer(self, text, **kw):
            self.sent.append(("text", text))

        async def answer_photo(self, photo, caption=None, **kw):
            self.sent.append(("photo", caption))

    monkeypatch.setattr(core, "client", Fake(), raising=False)
    monkeypatch.setattr(core, "normals", normals.Normals(tmp_path / "n.json"))
    p = Place("A", 51.18, 32.83)
    line = asyncio.run(core.norm_line(p, date(2026, 11, 14), {"temperature_2m_max": [15], "temperature_2m_min": [7]}))
    assert "теплее нормы" in line

    monkeypatch.setattr(core.saved, "list", lambda uid: [p, Place("B", 50.45, 30.52)])
    m = Msg()
    asyncio.run(places_router.send_compare(m, 1))
    assert m.sent[0][0] == "photo" and "Теплее всего сейчас: B" in m.sent[0][1]
