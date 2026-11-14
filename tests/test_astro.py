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


def test_twilight_line():
    t = astro_text(51.18, 32.83, DATA)
    line = next(x for x in t.splitlines() if x.startswith("🌄"))
    # Бахмач, 14.11: восход 07:03, заход 16:01 → гражданские сумерки примерно на 35–40 мин раньше и позже
    start, noon, end = (line.split(s)[1][:5] for s in ("Светает с ", "Полдень ", "Темнеет к "))
    assert "06:2" <= start <= "06:30" and "11:2" <= noon <= "11:35" and "16:3" <= end <= "16:40"


def test_no_twilight_in_polar_night():
    from datetime import timedelta, timezone

    from astral import Observer

    from astro import twilight_line
    # Шпицберген в декабре: солнце не поднимается и до −6°
    assert twilight_line(Observer(78.2, 15.6), date(2026, 12, 21), timezone(timedelta(hours=1))) is None
