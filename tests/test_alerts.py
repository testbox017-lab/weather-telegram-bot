from datetime import datetime, timedelta, timezone

import pytest

from alerts import ALERT_LIMIT, KINDS, OLD_KINDS, Alerts, changed, check_all, detect, promise, quiet
from weather import Place

P = Place("Бахмач", 51.18, 32.83)
NOW = datetime(2026, 11, 14, 13, 0, tzinfo=timezone.utc)


def make(now="2026-11-14T15:20", temp=5.0, temps=None, prec=None, prob=None, codes=None, gusts=None, tmax=None):
    t = [f"2026-11-14T{h:02d}:00" for h in range(24)] + [f"2026-11-15T{h:02d}:00" for h in range(24)]
    n = len(t)
    d = {"current": {"time": now, "temperature_2m": temp, "precipitation": 0.0},
         "hourly": {"time": t, "temperature_2m": temps or [temp] * n, "precipitation": prec or [0.0] * n,
                    "precipitation_probability": prob or [0] * n, "weather_code": codes or [3] * n,
                    "wind_speed_10m": [3] * n, "wind_gusts_10m": gusts or [5] * n}}
    if tmax:
        d["daily"] = {"time": ["2026-11-14", "2026-11-15"], "temperature_2m_max": tmax}
    return d


def at(hour, value, base, n=48):
    v = [base] * n
    v[hour] = value
    return v


def kinds(data):
    return {k for k, _, _ in detect(data)}


def test_calm_weather_no_events():
    assert detect(make()) == []


def test_frost_only_when_going_below_zero():
    ev = detect(make(temps=at(28, -3.2, 4.0)))
    assert ev == [("frost", "frost:2026-11-15", "❄️ Заморозок: до −3°C около 04:00")]
    assert "frost" not in kinds(make(temp=-2, temps=[-5.0] * 48))  # уже мороз — не спамим


def test_rain_soon():
    ev = detect(make(prec=at(16, 0.8, 0.0), prob=at(16, 70, 0)))
    assert ev == [("rain", "rain:2026-11-14T16", "☔️ Дождь начнётся около 16:00 (вероятность 70%)")]
    assert "rain" not in kinds(make(prec=at(15, 0.8, 0.0)))  # уже идёт
    assert "rain" not in kinds(make(prec=at(19, 0.8, 0.0)))  # не скоро


def test_storm_wind_heat_cold_jump():
    assert "storm" in kinds(make(codes=at(20, 95, 3)))
    ev = dict((k, t) for k, _, t in detect(make(gusts=at(18, 17.6, 5))))
    assert ev["wind"] == "💨 Порывы ветра до 18 м/с около 18:00"
    assert "heat" in kinds(make(temp=25, temps=at(17, 31.0, 25)))
    assert "cold" in kinds(make(temp=-15, temps=at(30, -22.0, -15)))
    ev = dict((k, t) for k, _, t in detect(make(tmax=[12, 3])))
    assert ev["jump"] == "🌡 Завтра на 9° холоднее: днём до +3°C"


def test_quiet_hours():
    assert quiet(make(now="2026-11-14T23:10")) and quiet(make(now="2026-11-14T06:59"))
    assert not quiet(make(now="2026-11-14T07:00"))


def test_store_add_toggle_limit(tmp_path):
    s = Alerts(tmp_path / "a.json")
    a = s.add(1, P)
    assert a["kinds"] == list(KINDS) and s.add(1, P)["id"] == a["id"]
    assert "frost" not in s.toggle(1, a["id"], "frost")["kinds"]
    assert Alerts(tmp_path / "a.json").get(1, a["id"])["kinds"] == [k for k in KINDS if k != "frost"]
    for i in range(ALERT_LIMIT - 1):
        assert s.add(1, Place(f"p{i}", i, i))
    assert s.add(1, Place("x", 80, 80)) is None
    assert s.remove(1, a["id"]) and s.get(1, a["id"]) is None


def test_no_repeats_and_rain_pause(tmp_path):
    s = Alerts(tmp_path / "a.json")
    a = s.add(1, P)
    events = [("storm", "storm:2026-11-14", "гроза"), ("rain", "rain:2026-11-14T16", "дождь 16")]
    assert s.new_events(a, events, NOW) == ["гроза", "дождь 16"]
    assert s.new_events(a, events, NOW + timedelta(minutes=30)) == []
    later_rain = [("rain", "rain:2026-11-14T18", "дождь 18")]
    assert s.new_events(a, later_rain, NOW + timedelta(hours=1)) == []  # не чаще раза в 3 ч
    assert s.new_events(a, later_rain, NOW + timedelta(hours=4)) == ["дождь 18"]
    s.toggle(1, a["id"], "storm")
    assert s.new_events(a, [("storm", "storm:2026-11-15", "гроза")], NOW) == []  # вид выключен


@pytest.mark.asyncio
async def test_check_all_shares_fetch_and_respects_quiet(tmp_path):
    s = Alerts(tmp_path / "a.json")
    s.add(1, P)
    s.add(2, P)
    fetched, sent = [], []

    async def fetch(place):
        fetched.append(place)
        return make(codes=at(20, 95, 3))

    async def send(uid, alert, texts):
        sent.append((uid, texts))

    assert await check_all(s, fetch, send, NOW) == 2
    assert len(fetched) == 1 and [u for u, _ in sent] == [1, 2] and "Гроза" in sent[0][1][0]
    assert await check_all(s, fetch, send, NOW) == 0  # уже отправлено

    async def night(place):
        return make(now="2026-11-14T23:30", gusts=at(23, 20, 5))

    assert await check_all(s, night, send, NOW) == 0


# ---------- Зимние предупреждения ----------

def with_hourly(data, **cols):
    data["hourly"].update(cols)
    return data


def test_freezing_rain_and_black_ice():
    ev = dict((k, t) for k, _, t in detect(make(codes=at(19, 66, 3))))
    assert ev["ice"] == "🧊 Ледяной дождь около 19:00 — на дорогах гололёд"
    # мокро при +1°, через 3 часа −2° → гололедица
    temps = [1.0] * 48
    temps[20:24] = [-2.0] * 4
    ev = detect(make(temp=1.0, temps=temps, prec=at(17, 0.5, 0.0)))
    ice = [e for e in ev if e[0] == "ice"]
    assert ice == [("ice", "ice:2026-11-14", "🧊 Гололедица: после осадков к 20:00 похолодает до −2°C")]
    assert "ice" not in kinds(make(temp=1.0, temps=temps))  # без осадков — не гололедица
    assert "ice" not in kinds(make(temp=3.0, prec=at(17, 0.5, 0.0)))  # мокро, но тепло


def test_heavy_snow():
    snow = [0.0] * 48
    snow[16:20] = [1.5, 2.0, 1.5, 1.0]
    ev = dict((k, t) for k, _, t in detect(with_hourly(make(), snowfall=snow)))
    assert ev["snow"] == "🌨 Сильный снег: около 6 см за 12 ч, начало около 16:00"
    snow[16:20] = [1.0, 1.0, 1.0, 0.5]
    assert "snow" not in kinds(with_hourly(make(), snowfall=snow))


def test_fog_by_code_and_visibility():
    assert dict((k, t) for k, _, t in detect(make(codes=at(21, 45, 3))))["fog"] == "🌫 Туман около 21:00"
    vis = [20000] * 48
    vis[18] = 180
    ev = dict((k, t) for k, _, t in detect(with_hourly(make(), visibility=vis)))
    assert ev["fog"] == "🌫 Туман около 18:00, видимость до 180 м"
    assert "fog" not in kinds(with_hourly(make(), visibility=[20000] * 48))


# ---------- «Прогноз изменился» ----------

def days(tmax, tmin, prec, start="2026-11-14"):
    nxt = (datetime.fromisoformat(start) + timedelta(days=1)).date().isoformat()
    return {"daily": {"time": [start, nxt], "temperature_2m_max": tmax, "temperature_2m_min": tmin,
                      "precipitation_sum": prec}}


def test_changed_temperature_and_rain():
    promised = promise(days([5, 3], [0, -1], [0, 0.2], start="2026-11-13"))
    assert promised == {"day": "2026-11-14", "tmax": 3, "tmin": -1, "prec": 0.2}
    assert changed(days([4, 0], [-2, 0], [0.4, 0]), promised) == []  # мелкие расхождения
    ev = changed(days([-2, 0], [-6, 0], [0, 0]), promised)
    assert ev == [("change", "change:2026-11-14", "🔄 Прогноз на сегодня изменился: вчера вечером обещали "
                   "−1…+3°, без осадков, теперь −6…−2°, без осадков")]
    ev = changed(days([3, 0], [-1, 0], [4.3, 0]), promised)
    assert ev[0][2].endswith("теперь −1…+3°, осадки 4 мм")
    assert changed(days([-2, 0], [-6, 0], [0, 0], start="2026-11-15"), promised) == []  # другой день
    assert changed(days([-2, 0], [-6, 0], [0, 0]), None) == []


@pytest.mark.asyncio
async def test_check_all_remembers_evening_and_warns_morning(tmp_path):
    s = Alerts(tmp_path / "a.json")
    s.add(1, P)
    sent = []

    async def send(uid, alert, texts):
        sent.append(texts)

    async def evening(place):
        return {**make(now="2026-11-13T19:00"), **days([5, 3], [0, -1], [0, 0], start="2026-11-13")}

    async def morning(place):
        return {**make(now="2026-11-14T07:10"), **days([-3, 0], [-8, 0], [0, 0])}

    await check_all(s, evening, send, NOW)
    assert Alerts(tmp_path / "a.json").list(1)[0]["promise"]["day"] == "2026-11-14"
    assert await check_all(s, morning, send, NOW) == 1 and sent[-1][0].startswith("🔄 Прогноз на сегодня")
    assert await check_all(s, morning, send, NOW) == 0  # один раз в день


def test_old_places_get_new_kinds(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"1": [{"id": 1, "name": "Б", "lat": 51.2, "lon": 32.8, "kinds": ["frost", "storm"]}]}',
                 encoding="utf-8")
    a = Alerts(f).list(1)[0]
    new = [k for k in KINDS if k not in OLD_KINDS]
    assert a["kinds"] == ["frost", "storm", *new]
    s = Alerts(f)
    s.toggle(1, 1, "fog")  # выключенный вручную новый вид не включается снова
    assert "fog" not in Alerts(f).list(1)[0]["kinds"]


# ---------- Давление и магнитные бури ----------

def test_pressure_jump():
    p = [1015.0] * 48
    p[15 + 24 - 1:] = [1003.0] * (48 - 38)  # за сутки −12 гПа ≈ −9 мм
    d = with_hourly(make(), pressure_msl=p)
    ev = dict((k, t) for k, _, t in detect(d))
    assert ev["pressure"] == "🧭 Давление резко падает: на 9 мм рт. ст. за сутки, к 15:00 до 752 мм"
    assert "pressure" not in kinds(with_hourly(make(), pressure_msl=[1015.0] * 48))


def test_magnetic_storm_alert():
    kp = [(datetime(2026, 11, 14, 18, tzinfo=timezone.utc), 6.0, "predicted")]
    d = make()
    d["utc_offset_seconds"] = 7200
    ev = dict((k, t) for k, _, t in detect(d, kp, NOW))
    assert ev["magnet"] == "🧲 Магнитная буря G2 (Kp 6) около 20:00"
    assert "magnet" not in kinds(d) and "magnet" not in {k for k, *_ in detect(d, [(kp[0][0], 3.0, "")], NOW)}
