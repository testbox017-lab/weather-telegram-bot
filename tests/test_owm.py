"""OpenWeatherMap (owm.py): перевод кодов, почасовой прогноз, наложение на Open-Meteo, /models, /settings."""
import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
import aiohttp  # noqa: E402
import pytest  # noqa: E402

import owm  # noqa: E402
from spread import SPREAD_MODELS, format_spread  # noqa: E402
from weather import Place, WeatherClient, format_forecast  # noqa: E402

PLACE = Place("Бахмач", 51.18, 32.83)
OFFSET = 7200  # Киев, зима
START = datetime(2026, 11, 16, 15, tzinfo=timezone.utc)  # 17:00 по Киеву


def om_response(days=7):
    """Ответ Open-Meteo с past_days=1: вчера + days дней, всё по нулям, чтобы видеть, что заменил OWM."""
    t0 = datetime(2026, 11, 15)
    hours = [(t0 + timedelta(hours=h)).isoformat(timespec="minutes") for h in range(24 * (days + 1))]
    n = len(hours)
    hourly = {"time": hours, **{k: [0] * n for k in (
        "temperature_2m", "precipitation_probability", "precipitation", "weather_code", "wind_speed_10m",
        "wind_gusts_10m", "wind_direction_10m", "relative_humidity_2m", "dew_point_2m")}}
    dn = days + 1
    daily = {"time": [(t0 + timedelta(days=d)).date().isoformat() for d in range(dn)],
             **{k: [0] * dn for k in ("weather_code", "temperature_2m_max", "temperature_2m_min",
                                      "precipitation_probability_max", "precipitation_sum", "wind_speed_10m_max",
                                      "wind_gusts_10m_max")},
             "sunrise": ["2026-11-16T07:10"] * dn, "sunset": ["2026-11-16T16:00"] * dn}
    current = {"time": "2026-11-16T17:00", "temperature_2m": 0, "apparent_temperature": 0, "relative_humidity_2m": 0,
               "weather_code": 0, "wind_speed_10m": 0, "is_day": 0, "uv_index": 0.0}
    return {"utc_offset_seconds": OFFSET, "current": current, "hourly": hourly, "daily": daily}


def owm_current():
    return {"weather": [{"id": 500}], "main": {"temp": 4.6, "feels_like": 1.2, "humidity": 90, "pressure": 1012,
                                               "sea_level": 1015},
            "wind": {"speed": 5.1, "deg": 220, "gust": 9.3}, "clouds": {"all": 100}, "visibility": 8000,
            "rain": {"1h": 0.4}}


def owm_forecast(n=40, rain_at=(2,)):
    items = []
    for i in range(n):
        item = {"dt": int((START + timedelta(hours=3 * i)).timestamp()),
                "main": {"temp": float(i % 8), "humidity": 80}, "wind": {"speed": 3.0, "deg": 180, "gust": 6.0},
                "weather": [{"id": 500 if i in rain_at else 804}], "pop": 0.7 if i in rain_at else 0.1}
        if i in rain_at:
            item["rain"] = {"3h": 1.5}
        items.append(item)
    return {"list": items}


def test_wmo_codes():
    assert owm.wmo_code(800) == 0 and owm.wmo_code(804) == 3 and owm.wmo_code(500) == 61
    assert owm.wmo_code(211) == 95 and owm.wmo_code(503) == 65 and owm.wmo_code(601) == 73
    assert owm.wmo_code(741) == 45 and owm.wmo_code(616) == 71 and owm.wmo_code(None) is None


def test_hourly_interpolates_in_local_time():
    rows = owm.hourly(owm_forecast(), OFFSET)
    first, last = min(rows), max(rows)
    assert first == "2026-11-16T17:00" and last == "2026-11-21T14:00"  # 40 точек × 3 ч
    assert rows["2026-11-16T17:00"]["temperature_2m"] == 0 and rows["2026-11-16T18:00"]["temperature_2m"] == 0.3
    assert rows["2026-11-16T20:00"]["temperature_2m"] == 1.0
    rain = rows["2026-11-16T23:00"]  # точка i=2 — 23:00 по Киеву; её дождь — на 22, 23 и 00 ч
    assert rain["weather_code"] == 61 and rain["precipitation"] == 0.5 and rain["precipitation_probability"] == 70
    assert sum(r["precipitation"] for r in rows.values()) == pytest.approx(1.5)
    assert rain["dew_point_2m"] is not None


def test_overlay_replaces_current_hourly_and_full_days():
    from weather import split_yesterday

    data = owm.overlay(split_yesterday(om_response()), owm_current(), owm_forecast())
    cur = data["current"]
    assert cur["temperature_2m"] == 4.6 and cur["pressure_msl"] == 1015 and cur["weather_code"] == 61
    assert cur["precipitation"] == 0.4 and cur["is_day"] == 0 and cur["uv_index"] == 0.0  # нет у OWM — Open-Meteo
    assert data["source"] == "owm"
    h = data["hourly"]
    i = h["time"].index("2026-11-16T20:00")
    assert h["temperature_2m"][i] == 1.0 and h["temperature_2m"][0] == 0  # 00:00 сегодня — Open-Meteo
    d = data["daily"]
    assert d["time"][0] == "2026-11-16"
    assert d["temperature_2m_max"][0] == 2.0 and d["precipitation_sum"][0] == 1.0  # 17–23 ч из OWM
    assert d["precipitation_sum"][1] == 0.5 and d["weather_code"][1] == 61  # остаток дождя после полуночи
    assert d["temperature_2m_max"][2] == 7.0
    assert d["temperature_2m_max"][6] == 0 and d["sunrise"][0] == "2026-11-16T07:10"  # 7-й день — Open-Meteo
    assert "Бахмач" in format_forecast("Бахмач", data, 7)


class FakeClient(WeatherClient):
    def __init__(self, fail_owm=None):
        self.fail_owm = fail_owm
        self.urls = []

    async def _get(self, url, params, **kw):
        self.urls.append((url, params))
        if url == owm.CURRENT_URL or url == owm.FORECAST_URL:
            if self.fail_owm:
                raise self.fail_owm
            return owm_current() if url == owm.CURRENT_URL else owm_forecast()
        return om_response()


@pytest.mark.asyncio
async def test_fetch_with_owm(monkeypatch):
    monkeypatch.setenv("OWM_API_KEY", "k")
    c = FakeClient()
    c.model_hook = lambda: "owm"
    data = await c.fetch(PLACE, 7)
    assert data["source"] == "owm" and data["current"]["temperature_2m"] == 4.6
    om = c.urls[0][1]
    assert "models" not in om  # «owm» — не модель Open-Meteo
    assert c.urls[1][1]["appid"] == "k" and c.urls[1][1]["units"] == "metric"


@pytest.mark.asyncio
async def test_fetch_falls_back_to_open_meteo(monkeypatch, caplog):
    monkeypatch.setenv("OWM_API_KEY", "secret-key")
    err = aiohttp.ClientResponseError(None, (), status=401, message="Unauthorized")
    c = FakeClient(fail_owm=err)
    c.model_hook = lambda: "owm"
    data = await c.fetch(PLACE, 1)
    assert data["source"] == "owm_failed" and data["current"]["temperature_2m"] == 0
    assert "401" in caplog.text and "secret-key" not in caplog.text

    monkeypatch.delenv("OWM_API_KEY")
    c = FakeClient()
    c.model_hook = lambda: "owm"
    assert (await c.fetch(PLACE, 1))["source"] == "owm_failed" and len(c.urls) == 1


@pytest.mark.asyncio
async def test_other_models_do_not_call_owm(monkeypatch):
    monkeypatch.setenv("OWM_API_KEY", "k")
    c = FakeClient()
    c.model_hook = lambda: "icon_seamless"
    data = await c.fetch(PLACE, 1)
    assert "source" not in data and len(c.urls) == 1 and c.urls[0][1]["models"] == "icon_seamless"


def test_models_series():
    from tests.test_radar_models_review import models_data

    data = models_data()
    data["utc_offset_seconds"] = OFFSET
    owm.add_series(data, owm_forecast())
    d = data["daily"]
    assert d["temperature_2m_max_owm"][0] is None  # сегодня у OWM только вечер
    assert d["temperature_2m_max_owm"][1] == 7.0 and d["temperature_2m_max_owm"][6] is None
    assert len(data["hourly"]["temperature_2m_owm"]) == len(data["hourly"]["time"])
    text = format_spread("Бахмач", data, SPREAD_MODELS + ["owm"])
    assert "OpenWeatherMap" in text and "(не все модели)" in text

    from charts import models_chart
    from spread import label

    models = SPREAD_MODELS + ["owm"]
    assert models_chart("Бахмач", data, models, {m: label(m) for m in models})[:4] == b"\x89PNG"


def test_settings_hide_owm_without_key(monkeypatch):
    from handlers.settings import settings_view
    import core

    monkeypatch.delenv("OWM_API_KEY", raising=False)
    text, markup = settings_view(501)
    buttons = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "cfg:model:owm" not in buttons and "OpenWeatherMap" not in text

    monkeypatch.setenv("OWM_API_KEY", "k")
    text, markup = settings_view(501)
    assert "cfg:model:owm" in [b.callback_data for row in markup.inline_keyboard for b in row]

    core.prefs.set(502, "model", "owm")
    monkeypatch.delenv("OWM_API_KEY")
    text, _ = settings_view(502)
    assert "не задан ключ" in text
