import math
from datetime import datetime, timedelta

from charts import compass, daily_chart, hourly_chart, wind_humidity_chart

START = datetime(2026, 11, 14)


def sample_data():
    hours = [START + timedelta(hours=i) for i in range(48)]
    days = [START + timedelta(days=i) for i in range(7)]
    return {
        "current": {"time": "2026-11-14T12:15"},
        "hourly": {
            "time": [h.isoformat(timespec="minutes") for h in hours],
            "temperature_2m": [3 + 3 * math.sin((i - 9) / 24 * 2 * math.pi) for i in range(48)],
            "precipitation_probability": [(i * 7) % 90 if i % 5 else None for i in range(48)],
            "precipitation": [0.0] * 48,
            "wind_speed_10m": [3 + (i % 7) * 0.8 for i in range(48)],
            "wind_gusts_10m": [7 + (i % 7) * 1.5 for i in range(48)],
            "wind_direction_10m": [(i * 23) % 360 for i in range(48)],
            "relative_humidity_2m": [60 + (i * 11) % 40 if i % 9 else None for i in range(48)],
        },
        "daily": {
            "time": [d.date().isoformat() for d in days],
            "temperature_2m_max": [6, 6, 4, 4, 7, 8, 9],
            "temperature_2m_min": [2, 0, -1, 1, 4, 6, 5],
            "precipitation_sum": [1.2, 0, 0, 3.4, 2.1, 5.0, None],
            "wind_speed_10m_max": [6.4, 3.0, 2.5, 8.1, 9.9, 4.0, 5.5],
            "wind_gusts_10m_max": [13.2, 5.9, 6.0, 15.0, 19.4, 9.0, None],
            "wind_direction_10m_dominant": [283, 244, 0, 90, 180, 135, 315],
            "relative_humidity_2m_mean": [82, 91, 75, 88, 95, 70, 66],
            "relative_humidity_2m_min": [65, 76, 60, 70, 85, 50, 48],
            "relative_humidity_2m_max": [94, 97, 90, 99, 100, 88, 80],
        },
    }


def is_png(b):
    return b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) > 10_000


def test_hourly_chart():
    assert is_png(hourly_chart("Бахмач, Черниговская область, Украина", sample_data()))


def test_daily_chart():
    assert is_png(daily_chart("Бахмач, Черниговская область, Украина", sample_data()))


def test_wind_humidity_hourly():
    assert is_png(wind_humidity_chart("Бахмач", sample_data(), 1))


def test_wind_humidity_daily():
    assert is_png(wind_humidity_chart("Бахмач", sample_data(), 7))


def test_compass():
    assert [compass(d) for d in (0, 44, 90, 180, 225, 350)] == ["С", "СВ", "В", "Ю", "ЮЗ", "С"]
