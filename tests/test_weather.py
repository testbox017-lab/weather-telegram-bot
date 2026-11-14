import pytest

from weather import Place, WeatherClient, format_forecast

CURRENT = {"temperature_2m": -3.4, "apparent_temperature": -8.1, "relative_humidity_2m": 81,
           "weather_code": 73, "wind_speed_10m": 4.26}
DAILY = {"time": ["2026-11-14", "2026-11-15"], "weather_code": [73, 0],
         "temperature_2m_max": [-1.2, 2.0], "temperature_2m_min": [-5.6, -4.0],
         "precipitation_probability_max": [90, None]}


def test_format_today():
    t = format_forecast("Москва", {"current": CURRENT, "daily": DAILY})
    assert "Москва" in t and "Снег" in t and "-3°C" in t and "-8°C" in t and "4.3 м/с" in t
    assert "-6…-1°C" in t and "90%" in t


def test_format_week():
    t = format_forecast("Москва", {"current": CURRENT, "daily": DAILY}, 2)
    assert "Сб 14.11" in t and "Вс 15.11" in t and "☔️ 0%" in t


class FakeClient(WeatherClient):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def _get(self, url, params):
        self.calls.append((url, params))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_find_city():
    c = FakeClient([{"results": [{"name": "Москва", "admin1": "Москва", "country": "Россия",
                                  "latitude": 55.75, "longitude": 37.62}]}])
    p = await c.find_city("Москва")
    assert p == Place("Москва, Россия", 55.75, 37.62)


@pytest.mark.asyncio
async def test_city_not_found():
    assert await FakeClient([{}]).find_city("Абырвалг") is None


@pytest.mark.asyncio
async def test_forecast_params():
    c = FakeClient([{"current": CURRENT, "daily": DAILY}])
    await c.forecast(Place("X", 1, 2), 7)
    assert c.calls[0][1]["forecast_days"] == 7 and c.calls[0][1]["wind_speed_unit"] == "ms"
