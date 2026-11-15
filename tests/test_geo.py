import pytest

from geo import BIG_CITY, MAX_CHOICES, candidates, split_query
from weather import Place, WeatherClient


def city(name, admin1=None, country="Украина", lat=51.0, lon=32.0, pop=None, admin2=None):
    return {"name": name, "admin1": admin1, "admin2": admin2, "country": country,
            "latitude": lat, "longitude": lon, "population": pop}


BAKHMACH = [
    city("Бахмач", "Черниговская область", lat=51.18, lon=32.83, pop=17000),
    city("Бахмач", "Сумская область", lat=50.9, lon=34.1, pop=300),
]


def test_split_query():
    assert split_query("Бахмач, Черниговская") == ("Бахмач", "Черниговская")
    assert split_query("Москва") == ("Москва", "")


def test_single_result_is_obvious():
    places, obvious = candidates([BAKHMACH[0]], "Бахмач")
    assert obvious and places == [Place("Бахмач, Черниговская область, Украина", 51.18, 32.83)]


def test_same_name_needs_choice():
    places, obvious = candidates(BAKHMACH, "бахмач")
    assert not obvious
    assert [p.name for p in places] == ["Бахмач, Черниговская область, Украина",
                                        "Бахмач, Сумская область, Украина"]


def test_big_city_is_picked_at_once():
    res = [city("Москва", "Москва", "Россия", 55.75, 37.62, pop=12_000_000),
           city("Москва", "Тверская область", "Россия", 57.0, 35.0, pop=50)]
    places, obvious = candidates(res, "Москва")
    assert obvious and places[0].name == "Москва, Россия"


def test_comparable_cities_need_choice():
    res = [city("Одесса", "Одесская область", pop=1_000_000, lat=46.48, lon=30.73),
           city("Одесса", "Техас", "США", 31.85, -102.37, pop=BIG_CITY)]
    assert candidates(res, "Одесса")[1] is False


def test_hint_filters_region_or_country():
    places, obvious = candidates(BAKHMACH, "Бахмач, сумская")
    assert obvious and places[0].lat == 50.9
    res = [city("Париж", "Иль-де-Франс", "Франция", 48.85, 2.35, pop=2_000_000),
           city("Париж", "Техас", "США", 33.66, -95.55, pop=25_000)]
    places, obvious = candidates(res, "Париж, США")
    assert obvious and places[0].name == "Париж, Техас, США"


def test_unknown_hint_is_ignored():
    assert len(candidates(BAKHMACH, "Бахмач, Марс")[0]) == 2


def test_exact_name_preferred_over_similar():
    res = [city("Бахмачевка", pop=50000, lat=1, lon=1), BAKHMACH[0]]
    places, obvious = candidates(res, "Бахмач")
    assert obvious and places[0].lat == 51.18


def test_duplicate_labels_use_district_then_coords():
    res = [city("Кировка", "Кировоградская область", admin2="Знаменский район", lat=48.5, lon=32.5),
           city("Кировка", "Кировоградская область", admin2="Голованевский район", lat=48.1, lon=30.4),
           city("Кировка", "Одесская область", lat=46.1, lon=30.1),
           city("Кировка", "Одесская область", lat=46.9, lon=29.9)]
    names = [p.name for p in candidates(res, "Кировка")[0]]
    assert names[0] == "Кировка, Знаменский район, Кировоградская область, Украина"
    assert names[1] == "Кировка, Голованевский район, Кировоградская область, Украина"
    assert names[2] == "Кировка, Одесская область, Украина (46.10, 30.10)"
    assert len(set(names)) == 4


def test_same_point_twice_and_limit():
    res = [city("Х", lat=10 + i, lon=10) for i in range(MAX_CHOICES + 5)] + [city("Х", lat=10.001, lon=10)]
    places, _ = candidates(res, "Х")
    assert len(places) == MAX_CHOICES and len({(p.lat, p.lon) for p in places}) == MAX_CHOICES


def test_nothing_found():
    assert candidates([], "Абырвалг") == ([], False)


class FakeClient(WeatherClient):
    def __init__(self, response):
        self.response, self.params = response, None

    async def _get(self, url, params):
        self.params = params
        return self.response


@pytest.mark.asyncio
async def test_find_cities_sends_name_without_hint():
    c = FakeClient({"results": BAKHMACH})
    places, obvious = await c.find_cities("Бахмач, Сумская")
    assert c.params["name"] == "Бахмач" and c.params["count"] > 1
    assert obvious and places[0].name == "Бахмач, Сумская область, Украина"


def test_osm_candidates_labels_and_dedup():
    from geo import osm_candidates

    rows = [
        {"lat": "51.18", "lon": "32.82", "name": "Бахмач-Пассажирский", "type": "station",
         "display_name": "Бахмач-Пассажирский, улица Вокзальная, Бахмач, Черниговская область, 16500, Украина"},
        {"lat": "51.181", "lon": "32.821", "name": "Бахмач-Пассажирский", "type": "station",
         "display_name": "дубль"},
        {"lat": "50.45", "lon": "30.52", "name": "", "type": "city", "display_name": "Киев, Украина"},
        {"lat": "bad"},
    ]
    places, obvious = osm_candidates(rows)
    assert [p.name for p in places] == ["Бахмач-Пассажирский (станция), Черниговская область, Украина",
                                        "Киев, Украина"]
    assert not obvious
