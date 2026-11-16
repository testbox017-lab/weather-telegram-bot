"""Радар (radar.py), сравнение моделей (spread.py, charts.models_chart) и итоги недели (review.py)."""
import asyncio
import io
import os
import tempfile
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
from PIL import Image  # noqa: E402

import radar  # noqa: E402
from charts import models_chart  # noqa: E402
from review import ForecastLog, format_review  # noqa: E402
from spread import SPREAD_MODELS, day_spread, format_spread, mark  # noqa: E402
from weather import Place  # noqa: E402

PLACE = Place("Бахмач", 51.18, 32.83)


def models_data(hi=(8, 9, 8), lo=(1, 2, 1), prec=(0, 0, 0), days=7):
    t0 = date(2026, 11, 16)
    daily = {"time": [(t0 + timedelta(days=i)).isoformat() for i in range(days)]}
    hourly = {"time": [(datetime(2026, 11, 16) + timedelta(hours=h)).isoformat(timespec="minutes")
                       for h in range(24 * days)]}
    for k, m in enumerate(SPREAD_MODELS):
        daily[f"temperature_2m_max_{m}"] = [hi[k]] * days
        daily[f"temperature_2m_min_{m}"] = [lo[k]] * days
        daily[f"precipitation_sum_{m}"] = [prec[k]] * days
        hourly[f"temperature_2m_{m}"] = [lo[k] + (hi[k] - lo[k]) * (h % 24) / 23 for h in range(24 * days)]
    return {"daily": daily, "hourly": hourly}


# ---------- Модели ----------

def test_models_agree():
    text = format_spread("Бахмач", models_data())
    assert text.count("✅") >= 7 and "согласны на всю неделю" in text
    assert "ECMWF" in text and "GFS" in text


def test_models_disagree_from_day():
    data = models_data()
    d = data["daily"]
    d["temperature_2m_max_gfs_seamless"][3:] = [15] * 4  # с четвёртого дня GFS теплее на 6–7°
    text = format_spread("Бахмач", data)
    assert "⚠️ Чт 19.11" in text and "согласны до чт 19.11" in text


def test_rain_doubt_and_missing_model():
    data = models_data(prec=(3.0, 0.0, 0.1))
    data["daily"]["temperature_2m_max_icon_seamless"][-1] = None
    s = day_spread(data["daily"], 0, SPREAD_MODELS)
    assert s["rain_doubt"] and mark(s) == "🟡"
    assert "(не все модели)" in format_spread("X", data)
    assert "💧 0.0–3.0 мм" in format_spread("X", data)


def test_models_chart_png():
    png = models_chart("Бахмач", models_data(), SPREAD_MODELS, {m: m for m in SPREAD_MODELS})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ---------- Радар ----------

def test_tile_math():
    x, y = radar.tile_xy(0, 0, 1)
    assert (x, y) == (1.0, 1.0)
    x, y = radar.tile_xy(51.18, 32.83)
    assert 75 < x < 76 and 42 < y < 44
    tiles = radar.needed_tiles(51.18, 32.83)
    assert 9 <= len(tiles) <= 16
    assert 0.7 < radar.km_per_px(51.18) < 0.8


def test_latest_frame_prefers_newest_past():
    maps = {"host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 100, "path": "/v2/radar/100"}, {"time": 200, "path": "/v2/radar/200"}],
                      "nowcast": [{"time": 300, "path": "/v2/radar/nowcast_300"}]}}
    assert radar.latest_frame(maps) == ("https://tilecache.rainviewer.com", 200, "/v2/radar/200")
    assert radar.latest_frame({"host": "h", "radar": {"past": []}}) is None


def _tile(color):
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), color).save(buf, format="PNG")
    return buf.getvalue()


def test_compose_draws_radar_over_map():
    coords = radar.needed_tiles(51.18, 32.83)
    tiles = {xy: (_tile((200, 220, 200, 255)), _tile((0, 0, 255, 255)) if i == 0 else None)
             for i, xy in enumerate(coords)}
    tiles[coords[1]] = (b"not a png", None)  # битый тайл не роняет картинку
    img = Image.open(io.BytesIO(radar.compose(51.18, 32.83, tiles)))
    assert img.size == (radar.SIZE, radar.SIZE)
    assert img.getpixel((radar.SIZE // 2, radar.SIZE // 2))[0] > 200  # красная точка в центре
    assert img.getpixel((2, 2))[2] > img.getpixel((2, 2))[0]  # левый верхний тайл синий от радара


def test_tile_cache_lru():
    c = radar.TileCache(2)
    c.put("a", b"1"), c.put("b", None), c.get("a"), c.put("c", b"3")
    assert c.get("b") is ... and c.get("a") == b"1" and c.get("c") == b"3"


def nowcast(values, snow=None, now="2026-11-15T10:00"):
    t0 = datetime(2026, 11, 15, 0, 0)
    times = [(t0 + timedelta(minutes=15 * i)).isoformat(timespec="minutes") for i in range(96)]
    prec = [0.0] * 96
    start = 40  # 10:00
    for i, v in enumerate(values):
        prec[start + i] = v
    return {"current": {"time": now}, "minutely_15": {"time": times, "precipitation": prec,
                                                      "snowfall": snow or [0.0] * 96}}


def test_nowcast_dry():
    assert "осадков не ожидается" in radar.nowcast_text(nowcast([]))


def test_nowcast_starts_later():
    text = radar.nowcast_text(nowcast([0, 0, 0.3, 0.6, 0.2]))
    assert "Дождь начнётся около 10:30" in text and "до ~11:15" in text and "0.6 мм" in text


def test_nowcast_raining_now_and_snow():
    snow = [0.0] * 96
    snow[40] = 0.2
    text = radar.nowcast_text(nowcast([0.4, 0.4, 0], snow=snow))
    assert "Сейчас идёт снег" in text and "закончится около 10:30" in text


def test_nowcast_missing():
    assert "нет" in radar.nowcast_text({})


# ---------- Итоги недели ----------

def forecast_resp(day0="2026-11-15", tmax=8.0, tmin=1.0, prec=0.0):
    d0 = date.fromisoformat(day0)
    return {"daily": {"time": [day0, (d0 + timedelta(days=1)).isoformat()],
                      "temperature_2m_max": [5.0, tmax], "temperature_2m_min": [0.0, tmin],
                      "precipitation_sum": [0.0, prec]}}


def past_resp(days=7, end="2026-11-15", tmax=8.0, tmin=1.0, prec=0.0):
    e = date.fromisoformat(end)
    times = [(e - timedelta(days=days - i)).isoformat() for i in range(days)]
    return {"daily": {"time": times, "temperature_2m_max": [tmax] * days, "temperature_2m_min": [tmin] * days,
                      "precipitation_sum": [prec] * days}}


def test_log_record_and_prune(tmp_path):
    log = ForecastLog(tmp_path / "log.json")
    assert log.record(PLACE, forecast_resp(), logged="2026-11-15") == "2026-11-16"
    assert log.logged_on(PLACE) == "2026-11-15"
    again = ForecastLog(tmp_path / "log.json")
    assert again.forecasts(PLACE)["2026-11-16"] == {"tmax": 8.0, "tmin": 1.0, "prec": 0.0}
    again.record(PLACE, forecast_resp("2026-12-31"))
    assert "2026-11-16" not in again.forecasts(PLACE)  # старше 35 дней
    assert again.record(PLACE, {"daily": {"time": ["2026-11-15"]}}) is None
    assert again.first_day() == "2027-01-01"


def test_log_sent_marks(tmp_path):
    log = ForecastLog(tmp_path / "log.json")
    log.mark_sent(7, "2026-11-15")
    assert ForecastLog(tmp_path / "log.json").sent(7) == "2026-11-15" and log.first_day() is None


def test_review_without_forecasts():
    text = format_review("Бахмач", past_resp(prec=1.0), {})
    assert "итоги недели 08.11–14.11" in text and "Пн 09.11: +1…+8°, 💧 1.0 мм" in text
    assert "💧 Осадки: 7.0 мм, 7 дн. из 7" in text and "появится через день" in text


def test_review_accuracy():
    past = past_resp(tmax=8.0, tmin=1.0, prec=0.0)
    fc = {"2026-11-13": {"tmax": 9.0, "tmin": 0.0, "prec": 0.0},  # ±1°, сухо — угадано
          "2026-11-14": {"tmax": 14.0, "tmin": 1.0, "prec": 3.0}}  # +6°, дождь не пошёл
    text = format_review("Бахмач", past, fc)
    assert "Пт 13.11: +1…+8°  ✅ прогноз 0…+9°" in text
    assert "Сб 14.11: +1…+8°  ❌ прогноз +1…+14°, с осадками" in text
    assert "(2 дн.): ошибка днём в среднем 3.5°, ночью 0.5°; осадки угаданы в 1 из 2" in text
    assert "Неделя без осадков" in text


def test_review_no_data():
    assert "Нет данных" in format_review("X", {"daily": {}}, {})


# ---------- Фоновая запись и отправка ----------

class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text))


def test_log_forecasts_once_per_day(tmp_path, monkeypatch):
    import core
    from handlers import extras

    monkeypatch.setattr(core, "forecast_log", ForecastLog(tmp_path / "log.json"))
    monkeypatch.setattr(extras, "tracked_places", lambda: [PLACE, Place("Киев", 50.45, 30.52)])
    calls = []

    async def fetch(p):
        calls.append(p.name)
        return forecast_resp()

    morning = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)
    evening = datetime(2026, 11, 15, 18, tzinfo=timezone.utc)
    assert asyncio.run(extras.log_forecasts(morning, fetch, pause=0)) == 0
    assert asyncio.run(extras.log_forecasts(evening, fetch, pause=0)) == 2
    assert asyncio.run(extras.log_forecasts(evening + timedelta(hours=4), fetch, pause=0)) == 0
    assert calls == ["Бахмач", "Киев"]


def test_tracked_places_dedup(monkeypatch):
    import core
    from handlers import extras

    monkeypatch.setattr(core.saved, "_data", {"1": [{"name": "Бахмач", "lat": 51.18, "lon": 32.83}]})
    monkeypatch.setattr(core.subs, "_data", {"1": [{"id": 1, "name": "Бахмач", "lat": 51.181, "lon": 32.829,
                                                    "sched": {}, "next": ""}]})
    monkeypatch.setattr(core.alerts, "_data", {"2": [{"id": 1, "name": "Киев", "lat": 50.45, "lon": 30.52}]})
    assert [p.name for p in extras.tracked_places()] == ["Бахмач", "Киев"]


def test_send_reviews_sunday_once(tmp_path, monkeypatch):
    import core
    from handlers import extras

    monkeypatch.setattr(core, "forecast_log", ForecastLog(tmp_path / "log.json"))
    monkeypatch.setattr(core.saved, "_data", {"1": [{"name": "Бахмач", "lat": 51.18, "lon": 32.83}],
                                              "2": [{"name": "Киев", "lat": 50.45, "lon": 30.52}]})
    monkeypatch.setattr(core.prefs, "_data", {"2": {"review": "off"}})

    class Client:
        async def fetch_past(self, place, days=7):
            return past_resp()

    monkeypatch.setattr(core, "client", Client(), raising=False)
    bot = FakeBot()
    sunday = datetime(2026, 11, 15, 18, 5, tzinfo=timezone.utc)
    assert asyncio.run(extras.send_reviews(bot, sunday - timedelta(hours=1))) == 0
    assert asyncio.run(extras.send_reviews(bot, datetime(2026, 11, 16, 18, 5, tzinfo=timezone.utc))) == 0
    assert asyncio.run(extras.send_reviews(bot, sunday)) == 1
    assert asyncio.run(extras.send_reviews(bot, sunday + timedelta(hours=1))) == 0
    assert bot.sent[0][0] == 1 and "итоги недели" in bot.sent[0][1]


def test_negative_precipitation_clipped():
    text = format_spread("Бахмач", models_data(prec=(-0.2, 1.5, 0.3)))
    assert "-0.2" not in text and "0.0–1.5 мм" in text
