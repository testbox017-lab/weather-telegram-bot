from advice import clothing, upcoming
from weather import format_forecast, format_hourly


def make(feels=3.0, wind=3.0, gust=5.0, prec=None, prob=None, codes=None, uv=None, now="2026-11-14T15:20"):
    t = [f"2026-11-14T{h:02d}:00" for h in range(24)] + [f"2026-11-15T{h:02d}:00" for h in range(24)]
    n = len(t)
    d = {"current": {"time": now, "temperature_2m": feels + 2, "apparent_temperature": feels,
                     "relative_humidity_2m": 70, "weather_code": 3, "wind_speed_10m": wind,
                     "wind_gusts_10m": gust, "precipitation": 0.0},
         "hourly": {"time": t, "temperature_2m": [feels + 2] * n, "precipitation": prec or [0.0] * n,
                    "precipitation_probability": prob or [0] * n, "weather_code": codes or [3] * n,
                    "wind_speed_10m": [wind] * n, "wind_gusts_10m": [gust] * n}}
    if uv is not None:
        d["daily"] = {"time": ["2026-11-14"], "uv_index_max": [uv]}
    return d


def wet_at(hour, n=48):
    prec = [0.0] * n
    prec[hour] = 1.2
    return prec


def test_upcoming_starts_at_current_hour():
    rows = upcoming(make(), 12)
    assert rows[0]["time"] == "2026-11-14T15:00" and len(rows) == 12 and rows[-1]["time"] == "2026-11-15T02:00"


def test_layers_by_feels_like():
    assert clothing(make(feels=-20)) == "👕 Пуховик, шапка, шарф и варежки"
    assert clothing(make(feels=3)) == "👕 Тёплая куртка и шапка"
    assert clothing(make(feels=15)) == "👕 Лёгкая куртка или свитер"
    assert clothing(make(feels=30)) == "👕 Лёгкая одежда, пейте больше воды"


def test_umbrella_snow_wind_uv():
    assert clothing(make(feels=10, prec=wet_at(18))) == "👕 Куртка или пальто, зонт"
    assert clothing(make(feels=10, prec=wet_at(30))) == "👕 Куртка или пальто"  # позже 12 часов
    assert clothing(make(feels=-3, prec=wet_at(16), codes=[73] * 48)) == \
        "👕 Тёплая куртка и шапка, непромокаемая обувь"
    assert clothing(make(feels=10, wind=11, prec=wet_at(16))) == \
        "👕 Куртка или пальто, капюшон или дождевик — зонт вывернет ветром"
    assert clothing(make(feels=10, gust=16)) == "👕 Куртка или пальто, одежда от ветра"
    assert clothing(make(feels=26, uv=7)) == "👕 Лёгкая одежда, пейте больше воды, крем от солнца и очки"


def test_no_current():
    assert clothing({}) is None


def test_advice_in_summary():
    assert "👕 Тёплая куртка и шапка" in format_forecast("Бахмач", make()).splitlines()[2]


def test_hourly_text():
    prob = [10] * 48
    prob[16] = 40
    lines = format_hourly("Бахмач", make(feels=5, prec=wet_at(16), prob=prob)).splitlines()
    assert lines[0] == "⏱ <b>Бахмач</b> — по часам"
    assert lines[2] == "15:00 ☁️ +7°, ☔️ 10%, 💨 3 м/с"
    assert lines[3] == "16:00 ☁️ +7°, ☔️ 40% 1.2 мм, 💨 3 м/с"
    assert len(lines) == 14


def test_hourly_no_data():
    assert "Нет почасовых данных" in format_hourly("X", {"current": {}})
