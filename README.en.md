# Weather Telegram Bot

[Русский](README.md) · **English**

[![tests](https://github.com/testbox017-lab/weather-telegram-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/testbox017-lab/weather-telegram-bot/actions/workflows/tests.yml)

A feature-rich Telegram weather bot built on [Open-Meteo](https://open-meteo.com) (free, no API key): current weather and forecasts with charts, saved places, scheduled forecasts, severe-weather warnings, air quality, precipitation radar and model comparison. Interface in Russian, Ukrainian or English.

Python 3.10+, aiogram 3, aiohttp, matplotlib. Runs in Docker or under systemd.

## Features

- **Weather by name**: send a city name and get the current weather and today's forecast: precipitation in the next 12 h, comparison with yesterday at the same time, wind with direction and gusts, pressure, cloud cover, UV index, visibility, and a "what to wear" tip. "⏱ Hourly" shows the next 12 hours as text.
- **7-day forecast**: `/week City`. Also `/weather City`, `/start`, `/help`.
- **Coordinates and geolocation**: `51.18, 32.83` or the "📍 My location" button. The last place is remembered, so "🌤 Weather now" and "📅 Weekly forecast" work without typing.
- **Ambiguous names**: if several places share a name, the bot offers buttons with region and country. You can also be explicit: `Bakhmach, Chernihiv`, `Paris, USA`.
- **Not only cities**: when Open-Meteo's geocoder finds nothing, the bot falls back to OpenStreetMap (Nominatim) for mountains, stations, lakes and landmarks.
- **My places** (up to 20): `/places`, `/add City`, `/add 51.18 32.83 [name]`, `/del`, and a "⭐ Save" button under every forecast. `/compare` shows all places in one message and one chart.
- **Weather on a date**: a calendar 16 days ahead and 14 days back, or `/date 21.11 [place]`, `tomorrow`, `yesterday`. Up to 16 days ahead is a forecast; earlier dates come from the Open-Meteo archive (back to 1940).
- **Scheduled forecasts**: `/subs`, `/subscribe [place] [3h | 08:00, 20:00]`. Every 1/3/6/12 h, daily, or up to 3 times a day in the place's time zone; weekdays only (`by weekdays 07:30`); full or short format; conditional (`07:00 if rain`, `snow`, `frost`, `below -5`, `above 25`). Up to 5 per user, silent at night.
- **Warnings**: `/alerts [place]`. The bot messages you about frost, precipitation in the next 1–2 h, thunderstorms, gusts from 15 m/s, heat from +30°, cold from −20°, or a daily temperature swing of 8°+; in winter also black ice, snowfall from 5 cm in 12 h and fog. "🔄 Forecast changed": the bot remembers tomorrow's forecast in the evening and tells you in the morning if it moved by 5°+ or rain appeared/disappeared. Checked every 30 minutes, each event once, silent at night.
- **Forecast source** (`/settings`): Open-Meteo model (Auto, ECMWF, ICON, GFS), an "Average" of ECMWF, ICON, GFS and OpenWeatherMap with a spread indicator, or OpenWeatherMap (needs `OWM_API_KEY`).
- **Air quality**: `/air [place]`: EAQI, PM2.5, PM10, NO₂, O₃, the next-24-hour trend and pollen (Europe only). Source: Open-Meteo (CAMS) or WAQI (needs `WAQI_TOKEN`).
- **3-day table**: `/table [place]`: morning, day, evening and night as monospaced text, wttr.in style.
- **Precipitation radar**: `/radar [place]`: the latest RainViewer radar image over an OpenStreetMap map, plus when rain or snow starts or stops within 3 hours (15-minute Open-Meteo forecast).
- **Model comparison**: `/models [place]`: ECMWF, ICON and GFS on one chart, with ✅ / 🟡 / ⚠️ agreement per day.
- **Weekend**: `/weekend [place]`: the coming Saturday and Sunday with a tip on which day is better.
- **Weekly review**: `/review [place]`: the past 7 days and how accurate the "tomorrow" forecast was. The bot logs forecasts every evening and sends a review on Sundays.
- **Climate normals**: a "📈 Usually…" line with 1991–2020 averages from the Open-Meteo archive.
- **Sun and moon**: dawn, solar noon, dusk (civil twilight), dew point, and hints about stuffiness, fog and black ice.
- **Pressure and geomagnetic storms**: the forecast shows the pressure trend ("falling, −6 mm in 12 h") and the Kp index from NOAA SWPC (free, no key). Alerts for a pressure change of 7 mmHg+ in 24 h and for a geomagnetic storm (Kp 5+, G1 and up).
- **Backup to Telegram**: every Sunday the bot sends its owner (`ADMIN_CHAT_ID` or the only user) a zip of the data JSON files, an off-server copy. `/backup` sends one now.
- **Health check**: `/ping` shows the bot's server, Telegram API and Open-Meteo response times. For Docker, the bot writes `heartbeat.json` every minute and `HEALTHCHECK` marks the container `unhealthy` if the scheduler or Telegram stalls.

## Running

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create `.env` next to `bot.py` (see `.env.example`) with `BOT_TOKEN=your_token` and run `python bot.py`. The `BOT_TOKEN` environment variable works too.

Optional `.env` keys: `OWM_API_KEY` (OpenWeatherMap), `WAQI_TOKEN` (WAQI air quality), `DATA_DIR` (where user data is stored; defaults to the folder with `bot.py`).

### Server 24/7

Docker (`docker compose up -d --build`) or systemd, step by step in [DEPLOY.md](DEPLOY.md) (in Russian). Only one instance may run per bot token.

### Windows

`start_bot.bat` starts the bot in a minimized window (logs in `bot.log`) and won't start a second copy; `stop_bot.bat` stops it.

## Code layout

- `bot.py`: entry point: dispatcher, routers, background jobs (scheduled forecasts and warnings).
- `core.py`: shared pieces: storage, Open-Meteo client, menu buttons, place selection, sending forecasts, input states (aiogram FSM).
- `handlers/`: aiogram routers: `places`, `dates`, `subs`, `settings`, `extras` (radar, models, review), `weather` (weather, air, weekend, /start, /help). `weather` is registered last because it treats any text as a place name.
- Other modules (`weather.py`, `places.py`, `subs.py`, `alerts.py`, …): logic without Telegram.
- `i18n.py` and `translations.py`: Russian source strings wrapped in `_()`, with Ukrainian and English translations.

## Tests

```bash
pip install pytest pytest-asyncio
pytest tests
```
