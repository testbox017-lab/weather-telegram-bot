"""Проверка моделей прогноза на живых данных Open-Meteo: python tools/check_sources.py [широта долгота]

Для каждой модели из prefs.MODELS запрашивает прогноз и прогоняет через все форматтеры и графики бота.
Печатает, какие поля модель не отдаёт (null), и падает ли что-нибудь. Ничего не меняет и не пишет.
Если задан WAQI_TOKEN — проверяет и ближайшую станцию WAQI.
"""
import asyncio
import os
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATA_DIR", str(Path(os.getenv("TEMP", "/tmp")) / "weather-bot-check"))
Path(os.environ["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

import aiohttp  # noqa: E402

from advice import is_wet, upcoming  # noqa: E402
from air import format_air, format_waqi  # noqa: E402
from alerts import detect  # noqa: E402
from core import render_charts  # noqa: E402
from handlers.dates import render_day_charts  # noqa: E402
from prefs import MODELS  # noqa: E402
from weather import Place, WeatherClient, format_day, format_forecast, format_hourly, format_short  # noqa: E402
from advice import dew_tips  # noqa: E402
from table import format_table  # noqa: E402
from weekend import compare_text, format_weekend  # noqa: E402


def nulls(block: dict | None) -> list[str]:
    out = []
    for k, v in (block or {}).items():
        if k == "time":
            continue
        if v is None or (isinstance(v, list) and v and all(x is None for x in v)):
            out.append(k)
    return out


async def main():
    lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (51.18, 32.83)
    place = Place("Проверка", lat, lon)
    failed = 0
    async with aiohttp.ClientSession() as session:
        client = WeatherClient(session)
        for model in MODELS:
            client.model_hook = lambda m=model: m
            print(f"\n=== {model} ===")
            steps = []
            try:
                d1 = await client.fetch(place, 1)
                d7 = await client.fetch(place, 9)
                day = date.today() + timedelta(days=3)
                dd = await client.fetch_day(place, day)
                for name, block in (("current", d1.get("current")), ("hourly", d1.get("hourly")),
                                    ("daily", d7.get("daily")), ("day.hourly", dd.get("hourly")),
                                    ("day.daily", dd.get("daily"))):
                    n = nulls(block)
                    print(f"  null в {name}: {', '.join(n) if n else 'нет'}")
                steps = [
                    ("format_forecast 1", lambda: format_forecast("X", d1, 1)),
                    ("format_forecast 7", lambda: format_forecast("X", d7, 7)),
                    ("format_short", lambda: format_short("X", d1)),
                    ("format_hourly", lambda: format_hourly("X", d1)),
                    ("charts 1", lambda: render_charts("X", d1, 1)),
                    ("charts 7", lambda: render_charts("X", d7, 7)),
                    ("weekend", lambda: format_weekend("X", d7)),
                    ("table", lambda: format_table("X", d7)),
                    ("dew_tips", lambda: dew_tips(d1)),
                    ("compare", lambda: compare_text([("X", d7), ("Y", d1)])),
                    ("alerts.detect", lambda: detect(d1)),
                    ("advice", lambda: [is_wet(h) for h in upcoming(d1, 12)]),
                    ("format_day", lambda: format_day("X", dd, day)),
                    ("day charts", lambda: render_day_charts("X", dd, day)),
                ]
            except Exception:
                failed += 1
                print("  ЗАПРОС УПАЛ:")
                traceback.print_exc()
            for name, fn in steps:
                try:
                    fn()
                    print(f"  ok  {name}")
                except Exception as e:
                    failed += 1
                    print(f"  FAIL {name}: {type(e).__name__}: {e}")
                    traceback.print_exc(limit=3)
            if steps:
                print("  --- сводка ---\n  " + format_forecast("X", d1, 1).replace("\n", "\n  "))
                if model == "best_match":
                    print("  --- таблица ---\n  " + format_table("X", d7).replace("\n", "\n  "))

        print("\n=== поиск мест (Open-Meteo, затем OpenStreetMap) ===")
        for q in ("Бахмач", "Говерла", "озеро Свитязь", "Бахмач-Пассажирский", "Эльбрус", "Абырвалгск"):
            try:
                places, obvious = await client.find_cities(q)
                shown = "; ".join(f"{p.name} ({p.lat:.3f}, {p.lon:.3f})" for p in places[:3]) or "не найдено"
                print(f"  {q!r}: {'сразу' if obvious else len(places)} → {shown}")
            except Exception as e:
                failed += 1
                print(f"  FAIL {q!r}: {type(e).__name__}: {e}")
        client.model_hook = lambda: None
        d1 = await client.fetch(place, 1)
        print("\n=== краткая сводка: все поля ===")
        from weather import SHORT_FIELDS
        print("  " + format_short("X", d1, list(SHORT_FIELDS)).replace("\n", "\n  "))

        print("\n=== air ===")
        try:
            format_air("X", await client.fetch_air(place))
            print("  ok  Open-Meteo")
        except Exception as e:
            failed += 1
            print(f"  FAIL Open-Meteo: {e}")
        token = os.getenv("WAQI_TOKEN", "").strip()
        if token:
            try:
                print("  " + format_waqi("X", await client.fetch_waqi(place, token), lat, lon).replace("\n", "\n  "))
            except Exception as e:
                failed += 1
                print(f"  FAIL WAQI: {e}")
        else:
            print("  WAQI_TOKEN не задан — WAQI пропущен")
    print(f"\nИтого ошибок: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
