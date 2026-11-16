"""Режим «Среднее» (ensemble.py): усреднение ECMWF, ICON, GFS и OpenWeatherMap."""
import copy

import aiohttp
import pytest

import ensemble
import owm
from tests.test_owm import OFFSET, PLACE, om_response, owm_current, owm_forecast
from weather import WeatherClient, format_forecast, split_yesterday


def multi_response(temps=(2.0, 4.0, 6.0)):
    """Тот же запрос с models=MEMBERS: у каждой модели свои ключи с суффиксом."""
    base = om_response()
    out = {"utc_offset_seconds": OFFSET, "current": {"time": base["current"]["time"]}}
    for name in ("hourly", "daily"):
        block = {"time": base[name]["time"]}
        for k, col in base[name].items():
            if k == "time" or not isinstance(col, list):
                continue
            for m, t in zip(ensemble.MEMBERS, temps):
                block[f"{k}_{m}"] = [t] * len(col)
        out[name] = block
    for k in base["current"]:
        if k != "time":
            for m, t in zip(ensemble.MEMBERS, temps):
                out["current"][f"{k}_{m}"] = t
    return out


def test_mean_of_three_models():
    data = ensemble.apply(split_yesterday(om_response()), split_yesterday(multi_response()))
    assert data["current"]["temperature_2m"] == 4.0 and data["current"]["relative_humidity_2m"] == 4
    assert set(data["hourly"]["temperature_2m"]) == {4.0}
    assert data["daily"]["temperature_2m_max"][0] == 4.0 and data["daily"]["precipitation_sum"][3] == 4.0
    assert data["daily"]["weather_code"][0] == 0  # код погоды — от «Авто»
    assert data["daily"]["sunrise"][0] == "2026-11-16T07:10"
    assert data["yesterday"]["hourly"]["temperature_2m"][0] == 4.0
    assert data["source"] == "mean" and data["spread_today"] == 4.0
    note = ensemble.note(data)
    assert "Среднее 3 источников (ECMWF, ICON, GFS)" in note and "расходятся до 4°" in note
    assert "Бахмач" in format_forecast("Бахмач", data, 7)


def test_mean_with_owm_and_missing_values():
    multi = multi_response()
    multi["hourly"]["temperature_2m_gfs_seamless"] = [None] * len(multi["hourly"]["time"])
    data = ensemble.apply(split_yesterday(om_response()), split_yesterday(multi), owm_current(), owm_forecast())
    h = data["hourly"]
    assert h["temperature_2m"][0] == 3.0  # 00:00 сегодня: OWM ещё нет, GFS пропал → ECMWF и ICON
    i = h["time"].index("2026-11-16T20:00")
    assert h["temperature_2m"][i] == pytest.approx((2 + 4 + 1.0) / 3, abs=0.01)  # OWM в 20:00 — +1°
    assert data["current"]["temperature_2m"] == pytest.approx((2 + 4 + 6 + 4.6) / 4, abs=0.01)
    assert data["daily"]["temperature_2m_max"][2] == pytest.approx((2 + 4 + 6 + 7) / 4, abs=0.01)
    assert data["daily"]["temperature_2m_max"][6] == 4.0  # у OWM нет 7-го дня
    assert "4 источников" in ensemble.note(data) and "OpenWeatherMap" in ensemble.note(data)


class FakeClient(WeatherClient):
    def __init__(self, fail=()):
        self.fail = fail
        self.urls = []

    async def _get(self, url, params, **kw):
        self.urls.append((url, dict(params)))
        kind = "owm" if url in (owm.CURRENT_URL, owm.FORECAST_URL) else "multi" if "models" in params else "base"
        if kind in self.fail:
            raise aiohttp.ClientConnectionError()
        if kind == "owm":
            return owm_current() if url == owm.CURRENT_URL else owm_forecast()
        return copy.deepcopy(multi_response() if kind == "multi" else om_response())


@pytest.mark.asyncio
async def test_fetch_mean(monkeypatch):
    monkeypatch.setenv("OWM_API_KEY", "k")
    c = FakeClient()
    c.model_hook = lambda: "mean"
    data = await c.fetch(PLACE, 7)
    assert data["source"] == "mean" and data["members"][-1] == "owm"
    assert sorted(p.get("models", "") for u, p in c.urls if "open-meteo" in u) == [
        "", "ecmwf_ifs025,icon_seamless,gfs_seamless"]


@pytest.mark.asyncio
async def test_fetch_mean_degrades(monkeypatch):
    monkeypatch.setenv("OWM_API_KEY", "k")
    c = FakeClient(fail=("owm",))
    c.model_hook = lambda: "mean"
    data = await c.fetch(PLACE, 1)
    assert data["source"] == "mean" and data["members"] == ensemble.MEMBERS

    c = FakeClient(fail=("multi",))
    c.model_hook = lambda: "mean"
    data = await c.fetch(PLACE, 1)
    assert data["source"] == "mean_failed" and data["current"]["temperature_2m"] == 0

    monkeypatch.delenv("OWM_API_KEY")
    c = FakeClient()
    c.model_hook = lambda: "mean"
    await c.fetch(PLACE, 1)
    assert not any("openweathermap" in u for u, _ in c.urls)

    c = FakeClient(fail=("base",))
    c.model_hook = lambda: "mean"
    with pytest.raises(aiohttp.ClientConnectionError):
        await c.fetch(PLACE, 1)


def test_current_from_hourly_when_models_have_no_current():
    multi = multi_response()
    multi["current"] = {"time": multi["current"]["time"]}  # Open-Meteo не прислал current по моделям
    data = ensemble.apply(split_yesterday(om_response()), split_yesterday(multi), owm_current(), owm_forecast())
    cur = data["current"]
    assert cur["temperature_2m"] == pytest.approx((2 + 4 + 6 + 4.6) / 4, abs=0.01)  # из почасовых на 17:00
    assert cur["apparent_temperature"] == pytest.approx((0 + 1.2) / 2)  # «ощущается» по часам нет: «Авто» + OWM
