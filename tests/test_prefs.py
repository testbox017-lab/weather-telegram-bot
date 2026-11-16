from prefs import DEFAULTS, Prefs, current_user
from weather import SHORT_DEFAULT

FULL = {**DEFAULTS, "short": SHORT_DEFAULT}


def test_defaults_and_set(tmp_path):
    p = Prefs(tmp_path / "prefs.json")
    assert p.get(1) == FULL and p.get(None) == FULL
    assert p.set(1, "model", "icon_seamless") and p.set(1, "air", "waqi")
    assert not p.set(1, "model", "bad") and not p.set(1, "colour", "red")
    assert Prefs(tmp_path / "prefs.json").get(1) == {"lang": "ru", "model": "icon_seamless", "air": "waqi", "review": "on",
                                                    "short": SHORT_DEFAULT}
    assert p.get(2) == FULL


def test_current_user(tmp_path):
    p = Prefs(tmp_path / "prefs.json")
    p.set(7, "air", "off")
    assert p.current()["air"] == "openmeteo"
    token = current_user.set(7)
    try:
        assert p.current()["air"] == "off"
    finally:
        current_user.reset(token)


def test_unknown_saved_value_falls_back(tmp_path):
    (tmp_path / "prefs.json").write_text('{"1": {"model": "old_model", "air": "waqi"}}', encoding="utf-8")
    assert Prefs(tmp_path / "prefs.json").get(1) == {"lang": "ru", "model": "best_match", "air": "waqi", "review": "on",
                                                    "short": SHORT_DEFAULT}


def test_toggle_short(tmp_path):
    p = Prefs(tmp_path / "prefs.json")
    assert p.toggle_short(1, "humidity") and "humidity" in p.get(1)["short"]
    assert p.toggle_short(1, "now") and "now" not in p.get(1)["short"]
    assert not p.toggle_short(1, "nonsense")
    for f in list(p.get(1)["short"])[:-1]:
        assert p.toggle_short(1, f)
    last = p.get(1)["short"]
    assert len(last) == 1 and not p.toggle_short(1, last[0])  # последнее поле не выключается
    assert Prefs(tmp_path / "prefs.json").get(1)["short"] == last
