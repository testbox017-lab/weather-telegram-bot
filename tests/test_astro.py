from datetime import date

from astro import astro_text, moon_phase, next_phases

DATA = {
    "utc_offset_seconds": 7200,
    "daily": {
        "time": ["2026-11-14", "2026-11-15"],
        "sunrise": ["2026-11-14T07:03", "2026-11-15T07:05"],
        "sunset": ["2026-11-14T16:01", "2026-11-15T16:00"],
        "daylight_duration": [32289.33, 32106.63],
    },
}


def test_full_and_new_moon():
    # полнолуние 24.11.2026, новолуние 09.12.2026
    assert moon_phase(date(2026, 11, 24))[1] == "Полнолуние"
    assert moon_phase(date(2026, 12, 9))[1] == "Новолуние"
    assert moon_phase(date(2026, 11, 24))[2] > 95
    assert moon_phase(date(2026, 12, 9))[2] < 5


def test_next_phases():
    names = {n: d for _, n, d in next_phases(date(2026, 11, 14))}
    assert names["Полнолуние"] == date(2026, 11, 24)
    assert names["Новолуние"] == date(2026, 12, 9)

def test_astro_text():
    t = astro_text(51.18, 32.83, DATA)
    assert "Восход 07:03" in t and "Заход 16:01" in t and "8 ч 58 мин" in t
    assert "Луна: восход" in t and "освещена на" in t
