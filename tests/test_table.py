from datetime import date, timedelta

from table import format_table, period_summary


def data(now="2026-11-14T13:20", days=4):
    start = date(2026, 11, 14)
    times = [f"{start + timedelta(days=k)}T{h:02d}:00" for k in range(days) for h in range(24)]
    n = len(times)
    temps = [float(i % 24) / 2 for i in range(n)]  # 0…11.5 в течение суток
    codes = [3] * n
    codes[24 + 15] = 95  # завтра в 15:00 гроза
    probs = [10] * n
    probs[24 + 16] = 80
    return {"current": {"time": now},
            "daily": {"time": [str(start + timedelta(days=k)) for k in range(days)]},
            "hourly": {"time": times, "temperature_2m": temps, "weather_code": codes,
                       "precipitation_probability": probs, "precipitation": [0.0] * n,
                       "wind_speed_10m": [3.4] * n}}


def test_period_summary_takes_worst_weather():
    s = period_summary(data()["hourly"], "2026-11-15", range(12, 18))
    assert s["code"] == 95 and s["prob"] == 80 and (s["tmin"], s["tmax"]) == (6.0, 8.5)
    night = period_summary(data()["hourly"], "2026-11-14", range(24, 30))  # 00–05 следующих суток
    assert (night["tmin"], night["tmax"]) == (0.0, 2.5)


def test_table_layout():
    text = format_table("Бахмач", data())
    assert text.startswith("📋 <b>Бахмач</b>") and "<pre>" in text and text.endswith("</pre>")
    body = text.split("<pre>")[1]
    today = body.split("\n\n")[0]
    assert "Сегодня" in today and "утро" not in today and "день" in today  # утро уже прошло
    assert "Вс 15.11" in body and "Пн 16.11" in body and "Вт 17.11" not in body
    assert "+6…+8°" in body and "80%" in body and "⛈" in body and "3 м/с" in body


def test_table_without_data():
    assert "Нет почасовых данных" in format_table("X", {"current": {}, "daily": {}, "hourly": {}})
