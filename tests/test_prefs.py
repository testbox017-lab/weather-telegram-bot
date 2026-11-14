from prefs import DEFAULTS, Prefs, current_user


def test_defaults_and_set(tmp_path):
    p = Prefs(tmp_path / "prefs.json")
    assert p.get(1) == DEFAULTS and p.get(None) == DEFAULTS
    assert p.set(1, "model", "icon_seamless") and p.set(1, "air", "waqi")
    assert not p.set(1, "model", "bad") and not p.set(1, "colour", "red")
    assert Prefs(tmp_path / "prefs.json").get(1) == {"model": "icon_seamless", "air": "waqi"}
    assert p.get(2) == DEFAULTS


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
    assert Prefs(tmp_path / "prefs.json").get(1) == {"model": "best_match", "air": "waqi"}
