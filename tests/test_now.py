"""Расширенная сводка «сейчас»: ветер, давление, УФ, видимость, осадки на 12 ч, сравнение со вчера."""
from weather import format_forecast, rain_outlook, split_yesterday, uv_text, visibility_text, wind_dir, yesterday_text


def hours(day, temps=None, prec=None, prob=None, codes=None):
    t = [f"{day}T{h:02d}:00" for h in range(24)]
    return {"time": t, "temperature_2m": temps or [0.0] * 24, "precipitation": prec or [0.0] * 24,
            "precipitation_probability": prob or [0] * 24, "weather_code": codes or [3] * 24}


def data(now="2026-11-14T15:30", today=None, **cur):
    current = {"time": now, "temperature_2m": 5.0, "apparent_temperature": 2.0, "relative_humidity_2m": 80,
               "weather_code": 3, "wind_speed_10m": 4.0, "precipitation": 0.0}
    current.update(cur)
    return {"current": current, "hourly": today or hours("2026-11-14")}


def test_wind_dir():
    assert wind_dir(0) == "↓ северный"
    assert wind_dir(225) == "↗ юго-западный" and wind_dir(200) == "↑ южный"
    assert wind_dir(359) == "↓ северный"
    assert wind_dir(None) == ""


def test_uv_and_visibility():
    assert "низкий" in uv_text(1.4)
    assert "крем" in uv_text(4)
    assert "экстремальный" in uv_text(11.6)
    assert uv_text(None) is None
    assert visibility_text(24000) is None
    assert visibility_text(4200) == "👁 Видимость 4.2 км"
    assert visibility_text(300) == "👁 Видимость 300 м — туман"


def test_no_rain():
    assert rain_outlook(data()) == "🌂 Без осадков ближайшие 9 ч"  # с 15:00 до конца данных


def test_rain_starts():
    prec = [0.0] * 24
    prec[18] = 0.6
    prob = [10] * 24
    prob[18] = 70
    assert rain_outlook(data(today=hours("2026-11-14", prec=prec, prob=prob))) == \
        "☔️ Дождь начнётся около 18:00 (вероятность 70%)"


def test_snow_now_and_stops():
    prec = [0.5] * 18 + [0.0] * 6
    codes = [73] * 24
    d = data(today=hours("2026-11-14", prec=prec, codes=codes), precipitation=0.4, weather_code=73)
    assert rain_outlook(d) == "☔️ Снег идёт, закончится около 18:00"


def test_split_yesterday_and_compare():
    raw = data(temperature_2m=9.4)
    y = hours("2026-11-13", temps=[5.0] * 24)
    t = raw["hourly"]
    raw["hourly"] = {k: y[k] + t[k] for k in t}
    raw["daily"] = {"time": ["2026-11-13", "2026-11-14"], "temperature_2m_max": [6, 10]}
    d = split_yesterday(raw)
    assert d["hourly"]["time"][0] == "2026-11-14T00:00" and len(d["hourly"]["time"]) == 24
    assert d["daily"] == {"time": ["2026-11-14"], "temperature_2m_max": [10]}
    assert yesterday_text(d) == "🔺 На 4° теплее, чем вчера в это время"
    d["current"]["temperature_2m"] = 5.3
    assert yesterday_text(d) == "↔️ Так же, как вчера в это время"


def test_split_without_past_days_keeps_data():
    d = data()
    assert split_yesterday(d)["hourly"]["time"][0] == "2026-11-14T00:00" and "yesterday" not in d


def test_full_summary():
    d = data(wind_direction_10m=230, wind_gusts_10m=11.2, pressure_msl=1013.0, cloud_cover=75,
             visibility=3000, uv_index=0.5)
    d["daily"] = {"time": ["2026-11-14"], "temperature_2m_min": [1], "temperature_2m_max": [7],
                  "precipitation_probability_max": [20], "uv_index_max": [2.1]}
    t = format_forecast("Бахмач", d)
    assert "🌂 Без осадков" in t.splitlines()[1]
    assert "4.0 м/с, ↗ юго-западный, порывы до 11 м/с" in t
    assert "760 мм рт. ст." in t and "Облачность: 75%" in t and "Видимость 3.0 км" in t
    assert "УФ-индекс до 2 — низкий" in t


def test_old_style_data_still_formats():
    t = format_forecast("X", {"current": {"temperature_2m": 1, "apparent_temperature": 0, "relative_humidity_2m": 50,
                                          "weather_code": 0, "wind_speed_10m": 1.0}})
    assert "Давление" not in t and "Ясно" in t


def test_short_format():
    from weather import format_short
    d = data(wind_speed_10m=3.6)
    d["daily"] = {"time": ["2026-11-14"], "temperature_2m_min": [1.2], "temperature_2m_max": [7.4],
                  "precipitation_probability_max": [20]}
    lines = format_short("Бахмач", d).splitlines()
    assert lines == ["📍 <b>Бахмач</b>: ☁️ Пасмурно, 5°C (ощущается 2°), 💨 4 м/с",
                     "🌂 Без осадков ближайшие 9 ч", "Сегодня 1…7°C, ☔️ 20%"]


def test_short_format_fields():
    from weather import format_short
    d = data(wind_speed_10m=3.6)
    d["current"].update(relative_humidity_2m=88, pressure_msl=1020)
    d["daily"] = {"time": ["2026-11-14"], "temperature_2m_min": [1.2], "temperature_2m_max": [7.4],
                  "precipitation_probability_max": [20]}
    assert format_short("Бахмач", d, ["humidity", "pressure"]) == "📍 <b>Бахмач</b>: 💧 88%, 🧭 765 мм"
    text = format_short("Бахмач", d, ["feels", "today", "advice"])
    assert text.splitlines()[0] == "📍 <b>Бахмач</b>: ощущается 2°" and "Сегодня 1…7°C" in text and "👕" in text
