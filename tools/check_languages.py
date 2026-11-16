"""Проверка языков на живых данных: python tools/check_languages.py [папка для графиков]

Для каждого языка (ru, uk, en) ищет места через Open-Meteo и OpenStreetMap, берёт прогноз и прогоняет его
через форматтеры бота: прогноз, кратко, по часам, на дату, выходные, таблица, воздух, радар, модели.
Печатает тексты, чтобы глазами проверить перевод, и считает ошибки; в английском ищет кириллицу
(кроме названий мест). Если указана папка — сохраняет в неё графики (PNG) каждого языка.
Ничего не отправляет в Telegram и не меняет данные бота.
"""
import asyncio
import os
import re
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATA_DIR", str(Path(os.getenv("TEMP", "/tmp")) / "weather-bot-check"))
Path(os.environ["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

import aiohttp  # noqa: E402

import core  # noqa: E402
from air import format_air  # noqa: E402
from astro import astro_text  # noqa: E402
from charts import models_chart  # noqa: E402
from handlers.dates import render_day_charts  # noqa: E402
from i18n import LANGS, use  # noqa: E402
from radar import nowcast_text  # noqa: E402
from spread import SPREAD_MODELS, format_spread, label  # noqa: E402
from table import format_table  # noqa: E402
from weather import WeatherClient, format_day, format_forecast, format_hourly, format_short  # noqa: E402
from weekend import format_weekend  # noqa: E402

QUERIES = {"ru": ["Бахмач", "Киев"], "uk": ["Бахмач", "Київ", "Говерла"], "en": ["Kyiv", "Bakhmach", "Hoverla"]}


async def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    async with aiohttp.ClientSession() as session:
        client = WeatherClient(session)
        core.client = client
        for code in LANGS:
            with use(code):
                print(f"\n==================== {code} ====================")
                place = None
                for q in QUERIES[code]:
                    try:
                        places, obvious = await client.find_cities(q)
                        print(f"поиск «{q}»: {[p.name for p in places][:3]}{' (сразу)' if obvious else ''}")
                        place = place or (places[0] if places else None)
                    except Exception:
                        failed += 1
                        print(f"FAIL поиск «{q}»\n{traceback.format_exc()}")
                if place is None:
                    failed += 1
                    continue
                names = {place.name, *place.name.split(", ")}
                try:
                    d1, d9 = await client.fetch(place, 1), await client.fetch(place, 9)
                    day = date.today() + timedelta(days=2)
                    dd = await client.fetch_day(place, day)
                    air = await client.fetch_air(place)
                    nowcast = await client.fetch_nowcast(place)
                    models = await client.fetch_models(place, SPREAD_MODELS, 7)
                except Exception:
                    failed += 1
                    print(f"FAIL запросы\n{traceback.format_exc()}")
                    continue
                steps = [
                    ("прогноз", lambda: format_forecast(place.name, d1, 1) + "\n\n" + astro_text(place.lat, place.lon,
                                                                                                d1)),
                    ("неделя", lambda: format_forecast(place.name, d9, 7)),
                    ("кратко", lambda: format_short(place.name, d1, None)),
                    ("по часам", lambda: format_hourly(place.name, d1)),
                    ("на дату", lambda: format_day(place.name, dd, day)),
                    ("выходные", lambda: format_weekend(place.name, d9)),
                    ("таблица", lambda: format_table(place.name, d9)),
                    ("воздух", lambda: format_air(place.name, air)),
                    ("радар", lambda: nowcast_text(nowcast)),
                    ("модели", lambda: format_spread(place.name, models)),
                    ("справка", core.help_text),
                ]
                for name, fn in steps:
                    try:
                        text = fn()
                    except Exception:
                        failed += 1
                        print(f"FAIL {name}\n{traceback.format_exc()}")
                        continue
                    print(f"\n--- {name} ---\n{text}")
                    if code == "en":
                        rest = text
                        for n in sorted(names, key=len, reverse=True):
                            rest = rest.replace(n, "")
                        for n in LANGS.values():
                            rest = rest.replace(n, "").replace(n.lower(), "")
                        bad = sorted({m.group(0) for m in re.finditer(r"\S*[а-яА-ЯёЁіїєґІЇЄҐ]\S*", rest)})
                        if bad:
                            failed += 1
                            print(f"FAIL кириллица в английском ({name}): {bad[:10]}")
                charts = [("today", lambda: core.render_charts(place.name, d1, 1)),
                          ("week", lambda: core.render_charts(place.name, d9, 7)),
                          ("date", lambda: render_day_charts(place.name, dd, day)),
                          ("models", lambda: [models_chart(place.name, models, SPREAD_MODELS,
                                                           {m: label(m) for m in SPREAD_MODELS})])]
                for name, fn in charts:
                    try:
                        pngs = fn()
                        if out_dir:
                            for i, png in enumerate(pngs):
                                (out_dir / f"{code}_{name}_{i}.png").write_bytes(png)
                        print(f"график {name}: ok ({len(pngs)} шт.)")
                    except Exception:
                        failed += 1
                        print(f"FAIL график {name}\n{traceback.format_exc()}")
    print(f"\nОшибок: {failed}")
    return failed


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
