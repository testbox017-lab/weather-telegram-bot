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

    async def _get(self, url, params, **kw):
        self.calls.append((url, params, kw))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_find_city():
    c = FakeClient([{"results": [{"name": "Москва", "admin1": "Москва", "country": "Россия",
                                  "latitude": 55.75, "longitude": 37.62}]}])
    p = await c.find_city("Москва")
    assert p == Place("Москва, Россия", 55.75, 37.62)


@pytest.mark.asyncio
async def test_city_not_found():
    c = FakeClient([{}, []])
    assert await c.find_city("Абырвалг") is None
    assert "nominatim" in c.calls[1][0] and "MyWeatherOpenMeteobot" in c.calls[1][2]["headers"]["User-Agent"]


@pytest.mark.asyncio
async def test_osm_fallback_finds_mountain():
    c = FakeClient([{}, [{"lat": "48.1602", "lon": "24.5002", "name": "Говерла", "category": "natural",
                         "type": "peak", "display_name": "Говерла, Ворохтянская поселковая громада, "
                                                         "Надворнянский район, Ивано-Франковская область, Украина"}]])
    places, obvious = await c.find_cities("Говерла")
    assert obvious and places == [Place("Говерла (вершина), Ивано-Франковская область, Украина", 48.1602, 24.5002)]
    assert c.calls[1][1]["q"] == "Говерла" and c.calls[1][1]["accept-language"] == "ru"


@pytest.mark.asyncio
async def test_osm_not_asked_when_city_found():
    c = FakeClient([{"results": [{"name": "Бахмач", "country": "Украина", "latitude": 51.18, "longitude": 32.83}]}])
    places, _ = await c.find_cities("Бахмач")
    assert places and len(c.calls) == 1


@pytest.mark.asyncio
async def test_forecast_params():
    c = FakeClient([{"current": CURRENT, "daily": DAILY}])
    await c.forecast(Place("X", 1, 2), 7)
    assert c.calls[0][1]["forecast_days"] == 7 and c.calls[0][1]["wind_speed_unit"] == "ms"


@pytest.mark.asyncio
async def test_model_param_from_hook():
    c = FakeClient([{"current": CURRENT, "daily": DAILY}] * 3)
    await c.fetch(Place("X", 1, 2), 1)
    assert "models" not in c.calls[0][1]
    c.model_hook = lambda: "ecmwf_ifs025"
    await c.fetch(Place("X", 1, 2), 1)
    assert c.calls[1][1]["models"] == "ecmwf_ifs025"
    from datetime import date
    await c.fetch_day(Place("X", 1, 2), date(2020, 1, 1), archive=True)
    assert "models" not in c.calls[2][1]  # у архива своя реанализ-модель


class FakeResponse:
    def __init__(self, status, body=None):
        self.status, self.body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        import aiohttp
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)

    async def json(self):
        return self.body


class FakeSession:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return FakeResponse(self.statuses.pop(0), {"ok": True})


@pytest.mark.asyncio
async def test_retry_on_503():
    s = FakeSession([503, 503, 200])
    c = WeatherClient(s)
    c.retry_delays = (0, 0)
    assert await c._get("u", {}) == {"ok": True} and s.calls == 3


@pytest.mark.asyncio
async def test_no_retry_on_400_and_gives_up():
    import aiohttp
    c = WeatherClient(FakeSession([400]))
    c.retry_delays = (0, 0)
    with pytest.raises(aiohttp.ClientResponseError):
        await c._get("u", {})
    s = FakeSession([503, 503, 503])
    c = WeatherClient(s)
    c.retry_delays = (0, 0)
    with pytest.raises(aiohttp.ClientResponseError):
        await c._get("u", {})
    assert s.calls == 3
