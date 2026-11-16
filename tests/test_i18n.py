"""Языки: у каждой строки есть перевод, подстановки совпадают, ответы на uk/en не содержат русского."""
import ast
import re
import string
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import i18n_keys  # noqa: E402

import i18n  # noqa: E402
from i18n import _, use  # noqa: E402
from translations import T  # noqa: E402

RU_ONLY = re.compile("[ыэъёЫЭЪЁ]")  # таких букв в украинском нет
CYRILLIC = re.compile("[а-яА-ЯёЁіїєґІЇЄҐ]")


def without_lang_names(text: str) -> str:
    """Названия языков пишутся каждое на своём языке — их не проверяем."""
    for name in i18n.LANGS.values():
        text = text.replace(name, "").replace(name.lower(), "")
    return text.replace("Язык · Мова", "")


def fields(s: str) -> set[str]:
    return {f for _lit, f, _spec, _conv in string.Formatter().parse(s) if f is not None}


def test_every_string_is_translated():
    keys, errors = i18n_keys.all_keys()
    assert not errors, errors
    missing = [k for k in keys if k not in T]
    assert not missing, f"нет перевода: {missing[:5]}"


def test_no_stale_translations():
    keys, _errors = i18n_keys.all_keys()
    stale = set(T) - set(keys)
    assert not stale, f"переводы строк, которых уже нет в коде: {sorted(stale)[:5]}"


@pytest.mark.parametrize("key", list(T))
def test_placeholders_match(key):
    uk, en = T[key]
    assert fields(uk) == fields(key) == fields(en), key
    assert uk.strip() and en.strip()


@pytest.mark.parametrize("key", list(T))
def test_translations_look_right(key):
    uk, en = T[key]
    assert not RU_ONLY.search(uk), f"русские буквы в украинском: {uk!r}"
    assert not CYRILLIC.search(without_lang_names(en)), f"кириллица в английском: {en!r}"


def test_no_local_underscore_in_translated_modules():
    """`kind, _, value = …` внутри функции делает _ локальной и ломает _("…") в этой функции."""
    for path in i18n_keys.source_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                targets = node.targets if isinstance(node, ast.Assign) else \
                    [node.target] if isinstance(node, (ast.For, ast.AsyncFor, ast.AugAssign, ast.AnnAssign)) else []
                names = [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]
                assert "_" not in names, f"{path.name}:{node.lineno} присваивает _"


def test_fallback_and_use():
    assert _("Ясно") == "Ясно"
    with use("en"):
        assert _("Ясно") == "Clear"
        assert _("Неизвестная строка") == "Неизвестная строка"
        assert _("🌡 {t}°C (ощущается как {feels}°C)", t=5, feels=2) == "🌡 5°C (feels like 2°C)"
    with use("uk"):
        assert i18n.wd(6) == "Нд" and i18n.wd_lower(0) == "пн"
    assert i18n.variants("🌤 Погода сейчас") == {"🌤 Погода сейчас", "🌤 Погода зараз", "🌤 Weather now"}


# ---------- Ответы целиком ----------

def sample_data():
    hours = [f"2026-11-14T{h:02d}:00" for h in range(24)] + [f"2026-11-15T{h:02d}:00" for h in range(24)]
    n = len(hours)
    return {
        "utc_offset_seconds": 7200,
        "current": {"time": "2026-11-14T15:30", "temperature_2m": 5.0, "apparent_temperature": 1.0,
                    "relative_humidity_2m": 80, "weather_code": 61, "wind_speed_10m": 6.0, "wind_gusts_10m": 12.0,
                    "wind_direction_10m": 200, "pressure_msl": 1012, "cloud_cover": 90, "visibility": 800,
                    "uv_index": 1, "precipitation": 0.3, "is_day": 1, "dew_point_2m": 4.5},
        "hourly": {"time": hours, "temperature_2m": [5.0] * n, "precipitation_probability": [70] * n,
                   "precipitation": [0.4] * n, "weather_code": [61] * n, "wind_speed_10m": [6.0] * n,
                   "wind_gusts_10m": [16.0] * n, "wind_direction_10m": [200] * n, "relative_humidity_2m": [80] * n,
                   "dew_point_2m": [4.0] * n},
        "daily": {"time": [f"2026-11-{d}" for d in range(14, 21)], "weather_code": [61, 3, 0, 71, 95, 2, 1],
                  "temperature_2m_max": [7, 6, 5, 2, 9, 8, 7], "temperature_2m_min": [1, 0, -2, -4, 3, 2, 1],
                  "precipitation_probability_max": [70, 20, 0, 80, 90, 10, 5],
                  "precipitation_sum": [3.0, 0, 0, 5.0, 8.0, 0, 0],
                  "sunrise": ["2026-11-14T07:05"] * 7, "sunset": ["2026-11-14T16:10"] * 7,
                  "daylight_duration": [32400] * 7, "wind_speed_10m_max": [8, 5, 3, 4, 12, 3, 2],
                  "wind_gusts_10m_max": [15, 9, 6, 7, 20, 6, 5], "wind_direction_10m_dominant": [200] * 7,
                  "relative_humidity_2m_mean": [80] * 7, "relative_humidity_2m_min": [60] * 7,
                  "relative_humidity_2m_max": [95] * 7, "uv_index_max": [1, 1, 2, 1, 1, 2, 2]},
    }


def rendered_texts() -> list[str]:
    """Много разных ответов бота на текущем языке (без сети)."""
    import air
    import alerts
    import astro
    import core
    import health
    import normals
    import radar
    import review
    import spread
    import subs
    import table
    import weekend
    from handlers import settings as settings_router, subs as subs_router
    from weather import format_day, format_forecast, format_hourly, format_short, SHORT_FIELDS

    d = sample_data()
    out = [format_forecast("X", d, 1), format_forecast("X", d, 7), format_hourly("X", d),
           format_short("X", d, list(SHORT_FIELDS)), format_day("X", d, date(2026, 11, 14), archive=True),
           astro.astro_text(51.18, 32.83, d), table.format_table("X", d), weekend.format_weekend("X", d),
           weekend.compare_text([("A", d), ("B", None), ("C", {**d, "current": {**d["current"], "temperature_2m": 9}})]),
           core.help_text()]
    out += [t for _k, _key, t in alerts.detect(d)]
    out += [alerts_text for alerts_text in (_(v) for v in alerts.KINDS.values())]
    out.append(air.format_air("X", {"current": {"european_aqi": 45, "pm2_5": 10, "pm10": 20, "birch_pollen": 150},
                                     "hourly": {"time": ["2026-11-14T16:00"], "european_aqi": [90]}}))
    out.append(air.format_waqi("X", {"city": {"name": "St", "geo": [51.18, 32.84]}, "aqi": 120,
                                     "time": {"s": "2026-11-14 15:00:00"}, "iaqi": {"pm25": {"v": 120}}},
                               51.18, 32.83, pollen={}))
    out.append(normals.norm_text({"11-14": [3.0, -2.0, 40]}, date(2026, 11, 14), 9, 4))
    norm = {"time": [f"2026-11-{d:02d}" for d in range(7, 14)], "temperature_2m_max": [5, 6, 7, 8, 9, 3, 2],
            "temperature_2m_min": [0, 1, 2, -1, 0, -3, -4], "precipitation_sum": [0, 2, 0, 0, 5, 0, 0]}
    out.append(review.format_review("X", {"daily": norm}, {"2026-11-08": {"tmax": 9, "tmin": 0, "prec": 1}}))
    out.append(review.format_review("X", {"daily": norm}, {}, "2026-11-01"))
    models = {"time": d["daily"]["time"]}
    for m, shift in zip(spread.SPREAD_MODELS, (0, 3, 6)):
        models[f"temperature_2m_max_{m}"] = [v + shift for v in d["daily"]["temperature_2m_max"]]
        models[f"temperature_2m_min_{m}"] = d["daily"]["temperature_2m_min"]
        models[f"precipitation_sum_{m}"] = [0, 0, 2, 0, 0, 0, 0]
    out.append(spread.format_spread("X", {"daily": models}))
    m15 = {"time": [f"2026-11-14T{15 + i // 4:02d}:{i % 4 * 15:02d}" for i in range(12)],
           "precipitation": [0, 0, 0.3, 0.5, 0.2, 0, 0, 0, 0, 0, 0, 0], "snowfall": [0] * 12}
    out.append(radar.nowcast_text({"minutely_15": m15, "current": {"time": "2026-11-14T15:00"}}))
    sub = {"sched": {"times": ["07:30"], "days": [0, 2]}, "cond": "below:-5", "short": True}
    out += [subs_router.sub_text(sub), subs.describe({"hours": 3}), subs.describe_cond("precip")]
    now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
    checks = [health.Check("Telegram API", True, 120, "HTTP 200"), health.Check("X", False, 5000, "нет ответа")]
    out.append(health.format_report(checks, now, version="dev", subs_total=1, next_send=now, tick=now))
    text, markup = settings_router.settings_view(1)
    out.append(text)
    out += [b.text for row in markup.inline_keyboard for b in row]
    text, markup = settings_router.alert_setup_view({"id": 1, "name": "X", "kinds": ["frost"]})
    out += [text] + [b.text for row in markup.inline_keyboard for b in row]
    out += [b.text for row in core.keyboard().keyboard for b in row]
    out += [b.text for row in core.forecast_markup(1, core.Place("X", 1, 2)).inline_keyboard for b in row]
    out += [c.description for c in core.bot_commands()]
    return out


def test_english_answers_have_no_russian(monkeypatch, tmp_path):
    import core
    from handlers import settings as settings_router

    store = core.Prefs(tmp_path / "prefs.json")
    monkeypatch.setattr(core, "prefs", store)
    monkeypatch.setattr(settings_router, "prefs", store)
    store.set(1, "lang", "en")
    with use("en"):
        texts = rendered_texts()
    for t in texts:
        assert not CYRILLIC.search(without_lang_names(t)), t
    joined = "\n".join(texts)
    for word in ("Feels like", "feels like", "Wind", "Sunrise", "Weekend", "Settings", "Mon", "km"):
        assert word in joined, word


def test_ukrainian_answers_have_no_russian_letters(monkeypatch, tmp_path):
    import core
    from handlers import settings as settings_router

    store = core.Prefs(tmp_path / "prefs.json")
    monkeypatch.setattr(core, "prefs", store)
    monkeypatch.setattr(settings_router, "prefs", store)
    with use("uk"):
        texts = rendered_texts()
    for t in texts:
        assert not RU_ONLY.search(without_lang_names(t)), t
    assert any("Відчувається" in t or "відчувається" in t for t in texts)


def test_language_follows_user_prefs(monkeypatch, tmp_path):
    import core
    from prefs import current_user

    store = core.Prefs(tmp_path / "prefs.json")
    monkeypatch.setattr(core, "prefs", store)
    store.set(7, "lang", "uk")
    token = current_user.set(7)
    try:
        assert _("Ясно") == "Ясно" and _("Пасмурно") == "Похмуро"
        assert core.keyboard().keyboard[0][1].text == "🌤 Погода зараз"
    finally:
        current_user.reset(token)
    assert _("Пасмурно") == "Пасмурно"  # другой пользователь — по умолчанию русский


def test_charts_render_in_english():
    import charts

    d = sample_data()
    with use("en"):
        assert charts.hourly_chart("X", d)[:4] == b"\x89PNG"
        assert charts.daily_chart("X", d)[:4] == b"\x89PNG"
        assert charts.wind_humidity_chart("X", d, 7)[:4] == b"\x89PNG"
        assert charts.compass(90) == "E"


def test_input_words_in_all_languages():
    from dates import parse_date
    from subs import parse_condition, parse_schedule, split_condition, split_short

    today = date(2026, 11, 16)
    assert parse_date("tomorrow", today) == parse_date("завтра", today) == date(2026, 11, 17)
    assert parse_date("вчора", today) == parse_date("yesterday", today) == date(2026, 11, 15)
    assert parse_date("сьогодні", today) == today
    assert parse_schedule("every 3 h") == parse_schedule("кожні 3 год") == parse_schedule("3h") == {"hours": 3}
    weekdays = {"times": ["07:30"], "days": [0, 1, 2, 3, 4]}
    assert parse_schedule("weekdays 07:30") == parse_schedule("по буднях о 07:30") == weekdays
    assert parse_schedule("по будням в 07:30") == weekdays
    assert parse_schedule("sat sun 10:00") == parse_schedule("сб нд 10:00") == {"times": ["10:00"], "days": [5, 6]}
    assert parse_schedule("08:00 and 20:00") == parse_schedule("08:00 та 20:00") == {"times": ["08:00", "20:00"]}
    assert split_condition("Kyiv 07:00 if rain") == ("Kyiv 07:00", "precip", True)
    assert split_condition("Київ 07:00 якщо нижче -5") == ("Київ 07:00", "below:-5", True)
    assert parse_condition("snow") == parse_condition("сніг") == "snow"
    assert parse_condition("above 25°C") == parse_condition("вище 25") == "above:25"
    assert parse_condition("frost") == "frost" and parse_condition("ниже -5°С") == "below:-5"
    assert split_short("Kyiv 3h short") == ("Kyiv 3h", True) and split_short("Київ стисло")[1]
