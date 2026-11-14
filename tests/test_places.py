import json

from places import DEFAULT_NAME, FAV_LIMIT, Favorites, LastPlaces, build_cb, coords_name, parse_cb, parse_coords
from weather import Place


def test_cb_roundtrip():
    data = build_cb(7, 55.755826, 37.6173)
    assert data == "w:7:55.756:37.617"
    assert parse_cb(data) == (7, 55.756, 37.617)


def test_cb_fits_64_bytes():
    assert len(build_cb(7, -89.999999, -179.999999).encode()) <= 64


def test_cb_rejects_bad_data():
    for bad in [None, "", "x:1:1:1", "w:3:1:1", "w:1:abc:1", "w:1:95:1", "w:1:1:200", "w:1:1"]:
        assert parse_cb(bad) is None


def test_last_places_persist(tmp_path):
    path = tmp_path / "last_places.json"
    store = LastPlaces(path)
    assert store.get(42) is None
    store.set(42, Place("Казань", 55.79, 49.12))
    assert json.loads(path.read_text(encoding="utf-8"))["42"]["name"] == "Казань"
    again = LastPlaces(path)  # как после перезапуска
    assert again.get(42) == Place("Казань", 55.79, 49.12)
    assert again.name_for(42, 55.790, 49.120) == "Казань"
    assert again.name_for(42, 10.0, 10.0) == DEFAULT_NAME
    assert again.name_for(7, 55.79, 49.12) == DEFAULT_NAME


def test_last_places_broken_file(tmp_path):
    path = tmp_path / "last_places.json"
    path.write_text("{не json", encoding="utf-8")
    store = LastPlaces(path)
    assert store.get(1) is None
    store.set(1, Place("Сочи", 43.6, 39.73))
    assert LastPlaces(path).get(1).name == "Сочи"


def test_parse_coords_formats():
    assert parse_coords("51.18, 32.83") == (51.18, 32.83, "")
    assert parse_coords("51.18 32.83") == (51.18, 32.83, "")
    assert parse_coords("51,18 32,83") == (51.18, 32.83, "")
    assert parse_coords("51.18,32.83") == (51.18, 32.83, "")
    assert parse_coords("-33.9 18.4 Кейптаун") == (-33.9, 18.4, "Кейптаун")
    assert parse_coords("51 32") == (51.0, 32.0, "")


def test_parse_coords_invalid():
    for bad in [None, "", "Москва", "91 10", "10 181", "-91, 0", "51.18", "abc 1"]:
        assert parse_coords(bad) is None, bad


def test_coords_name():
    assert coords_name(51.181, 32.835) == "Точка 51.18, 32.84"


def test_favorites_add_dedupe_delete(tmp_path):
    path = tmp_path / "saved_places.json"
    fav = Favorites(path)
    assert fav.add(1, Place("Бахмач", 51.18, 32.83)) == "added"
    assert fav.add(1, Place("Бахмач", 51.18, 32.83)) == "exists"
    assert fav.add(1, Place("Бахмач, центр", 51.1801, 32.8302)) == "updated"   # те же координаты
    assert fav.add(1, Place("бахмач, ЦЕНТР", 51.2, 32.9)) == "updated"         # то же имя
    assert fav.add(1, Place("Киев", 50.45, 30.52)) == "added"
    assert [p.name for p in Favorites(path).list(1)] == ["бахмач, ЦЕНТР", "Киев"]  # пережило перезапуск
    assert fav.list(2) == []
    assert fav.remove_by(1, "киев").name == "Киев"
    assert fav.remove_by(1, "5") is None
    assert fav.remove_by(1, "1").lat == 51.2
    assert fav.list(1) == []


def test_favorites_limit(tmp_path):
    fav = Favorites(tmp_path / "s.json")
    for i in range(FAV_LIMIT):
        assert fav.add(1, Place(f"P{i}", i, i)) == "added"
    assert fav.add(1, Place("лишнее", 80, 80)) == "full"
    assert len(fav.list(1)) == FAV_LIMIT


def test_fav_callback_fits():
    assert len(f"fa:{-89.9999:.3f}:{-179.9999:.3f}".encode()) <= 64
