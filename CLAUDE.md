# CLAUDE.md — погодный Telegram-бот

Пиши пользователю (Дмитрий) по-русски. Бот **для личного использования**: не добавляй фичи «для масштаба»
(мультипользовательность, SQLite, антифлуд, статистика), пока он сам не попросит.

## Что это
Telegram-бот @MyWeatherOpenMeteobot на Python 3 + aiogram 3. Погода от Open-Meteo (бесплатно, без ключа),
дополнительно OpenWeatherMap и WAQI (по желанию, ключи в `.env`). Отвечает на название города, координаты
или геолокацию сводкой «сейчас + сегодня» с графиками matplotlib и inline-кнопками. Полный список
возможностей — в `README.md` (есть `README.en.md`).

Основное: погода сейчас/неделя/на дату (архив с 1940), «Мои места», рассылки по расписанию (с днями
недели и условиями), предупреждения (заморозок, гроза, порывы, жара, гололёд, снегопад, туман,
«прогноз изменился»…), качество воздуха и пыльца,
таблица на 3 дня, выходные, радар осадков (RainViewer + OSM), сравнение моделей ECMWF/ICON/GFS,
итоги недели (точность прогноза), сравнение мест, климатическая норма 1991–2020, `/ping`,
`/settings` (модель прогноза, источник воздуха, поля краткой сводки, язык), языки ru/uk/en.

## Структура
- `bot.py` — только запуск: диспетчер, роутеры, фоновые задачи (рассылки, предупреждения, heartbeat).
- `core.py` — общее: хранилища, `core.client` (WeatherClient), кнопки меню, `with_place`, `build_weather`,
  FSM `Input.place/date/sub_time`, `ResetInputMiddleware`, `CurrentUserMiddleware` (contextvar текущего
  пользователя для prefs), `send_prompt`/`drop_prompt`.
- `handlers/` — роутеры aiogram: `places`, `dates`, `subs`, `settings` (настройки, предупреждения, /ping),
  `extras` (радар, модели, итоги недели, логгер прогнозов), `weather` (погода, воздух, выходные, /start,
  /help). **`weather` подключается последним** — его обработчик ловит любой текст как город.
- Логика без Telegram: `weather.py` (клиент Open-Meteo, retry), `geo.py` (геокодер + Nominatim fallback,
  1 запрос/с, свой User-Agent), `places.py`, `subs.py`, `alerts.py`, `advice.py` (что надеть), `air.py`,
  `astro.py` (солнце, сумерки), `charts.py`, `table.py`, `weekend.py`, `normals.py`, `radar.py`,
  `spread.py` (разброс моделей), `review.py` (ForecastLog), `owm.py`, `ensemble.py` («Среднее»),
  `prefs.py`, `dates.py`, `databackup.py` (бэкап в Telegram), `health.py` + `healthcheck.py` (Docker HEALTHCHECK по `heartbeat.json`).
- `i18n.py` + `translations.py` — переводы (см. правило ниже).
- `tools/` — живые проверки: `check_sources.py` (все модели), `check_languages.py`, `i18n_keys.py --missing en`.
- `deploy/` — `deploy.sh`, `backup.sh`, `watchdog.sh`, `install-server.sh`, `install-watchdog.sh`, systemd-юнит.
- `tests/` — ~230 тестов pytest, включая `test_flows.py` (настоящий диспетчер с фейковой сессией Telegram).
- Windows: `start_bot.bat` / `stop_bot.bat` / `backup_pull.bat` (скачать свежий бэкап с сервера).

Данные пользователей (JSON в `DATA_DIR`, на сервере `/opt/weather-bot/data`, в git не попадают):
`last_places.json`, `saved_places.json`, `subscriptions.json`, `alerts.json`, `prefs.json`,
`normals.json`, `forecast_log.json`, `heartbeat.json`.

Префиксы callback-данных: `pk:` выбор города, `r:` обновить, `hr:` по часам, `al:` предупреждения,
`pl:ask:` подтверждение удаления места, `su:` рассылки (и `^s[hti]:`), `cfg:` настройки (не `st:` —
конфликтовал с рассылками), `rd:` радар, `md:` модели, `rv:` итоги. Новый префикс проверяй на пересечения.

## Как запускать
Локально (ПК Дмитрия, `D:\Program\prg_py\Weather_bot`):
- Python — `D:\Program\thonny\python.exe` (3.14). Обычный `python` в удалённых сессиях — заглушка MS Store.
- `.env` рядом с `bot.py`: `BOT_TOKEN` (обязательно), `WAQI_TOKEN`, `OWM_API_KEY`, `DATA_DIR`, `ADMIN_CHAT_ID`
  — образец в `.env.example`. **Ключи никогда не коммить и не вставлять в чаты/логи.**
- ⚠️ **Не запускай бота на ПК, пока работает сервер** — один токен = один экземпляр, иначе
  `TelegramConflictError`. Бот на Windows сейчас остановлен.

Тесты:
```bash
pip install -r requirements.txt pytest pytest-asyncio
MPLBACKEND=Agg python -m pytest tests -q
```
CI гоняет тесты на 3.12 и 3.14 + сборку Docker. Нужны тесты на каждую новую фичу.
Живая проверка в Telegram: web.telegram.org в Chrome Дмитрия (Claude in Chrome). Ввод «/cmd аргументы» +
Enter отправляет только «/cmd» (автодополнение съедает аргументы) — пользуйся inline-кнопками.
Тестовые места/рассылки после проверки удаляй.

## Деплой (важно)
- Сервер: Hetzner VPS, Ubuntu 26.04, 2 vCPU / 3.7 ГБ RAM / 19 ГБ диск, TZ сервера UTC. Docker compose в
  `/opt/weather-bot` (это git-checkout `main`), контейнер на Python 3.14, `restart: unless-stopped`,
  `.env` доступен только root. Доступ: `ssh root@<сервер>` ключом `~/.ssh/id_ed25519` с ПК Дмитрия.
- **Автодеплой: каждый push в `main`, прошедший CI, сразу выкатывается на сервер** (GitHub Actions,
  ограниченный ключ с `command=/usr/local/bin/weather-bot-deploy`). **Push в main = релиз — всегда спрашивай
  Дмитрия перед push/merge.** Обычный путь: ветка → PR → его «да» → merge → CI + deploy зелёные.
  Ручной передеплой: `gh workflow run tests.yml --ref main`.
- Бэкап: `weather-bot-backup`, cron 03:30 UTC → `/var/backups/weather-bot` (14 копий, весь `data/`).
  Плюс копия вне сервера: бот по воскресеньям с 09:00 UTC шлёт владельцу zip JSON-ов (`databackup.py`,
  метка `backup_sent.json`), `/backup` — сейчас.
- Сторож `weather-bot-watchdog` (cron */5, вне контейнера): контейнер/рестарты, ERROR в логах, бэкап >26 ч,
  диск >80 %, сбои Open-Meteo, перезагрузка. Пишет в `ADMIN_CHAT_ID` или единственному пользователю.
- Отдельно на сервере есть **чужой для репо** `monitor_bot` (`/opt/monitor_bot`, systemd `monitor-bot.service`)
  — он шлёт «🌐 Сетевые ошибки» / «⚠ Ошибки в логах». Решено оставить как есть.
- `unattended-upgrades` с авто-перезагрузкой в 02:00 UTC; бот поднимается сам.
- Любые изменения на сервере (`.env`, cron, ssh) — только с явного согласия Дмитрия.

## Правила кода
- **i18n:** каждая видимая пользователю строка — через `_()` (ключ — русский текст, параметры через kw)
  или `N_()` для констант, и с записью в `translations.py` (`T = {"рус": ("укр", "eng")}`).
  Иначе падает `tests/test_i18n.py`. Проверка: `python tools/i18n_keys.py --missing en`.
  **Никогда не используй `_` как «мусорную» переменную** — затеняет `_()`. Тексты сторожа и логов — на русском.
- Тесты подменяют `core.client` и модули `handlers.*` через monkeypatch — держи зависимости через модуль,
  а не `from x import y`, иначе патч не сработает.
- В `Dockerfile` копируются `*.py` и `handlers/` — новую папку с кодом добавь туда.
- Окончания строк — LF (`charts.py` раньше был CRLF; старые патчи могут требовать `git am --ignore-whitespace`).
- Коммиты от `356609369+testbox017-lab@users.noreply.github.com`. Репозиторий публичный — без секретов.

## Решения и почему
- **Только личное использование** → многопользовательские пункты роадмапа отложены (см. ниже).
- **Open-Meteo** — основной источник: бесплатно, без ключа, есть архив, модели, воздух, нормы.
- **Воздух по умолчанию Open-Meteo (CAMS)**: WAQI подключён, но рядом с Бахмачом/Киевом нет живых станций
  (ближайшая ~500 км).
- **OpenWeatherMap** — опциональная модель поверх Open-Meteo (дальше 5 дней, восход, УФ — из Open-Meteo);
  без ключа пункт скрыт. Облачный контейнер Claude не достаёт до api.openweathermap.org — проверять на ПК.
- **«Среднее»** (`ensemble.py`): ECMWF+ICON+GFS+OWM. Подвох: у Open-Meteo в мультимодельном запросе `current`
  общий (первой модели), поэтому «сейчас» каждой модели берётся из hourly на текущий час.
- **Sinoptik не сделан** — нет API. Региональная карта погоды — пропущена.
- **WhatsApp/Viber не делаем** — платно (WhatsApp Business API, Viber-боты с 2024), для личного бота не стоит.
- Тихие часы 23–7 по местному времени для рассылок «каждые N ч» и предупреждений.
- Сбои отправки рассылок по сети (`TelegramNetworkError` timeout) — повтор через 5 мин до 2 раз (`subs.RETRY_*`).
- Ночные (~01:10 UTC) кратковременные Bad Gateway/Flood со стороны Telegram и короткие обрывы IPv4 —
  норма, сообщения не теряются; контейнер работает только по IPv4. Алерты monitor_bot об этом не трогаем.

## История (кратко)
MVP → выбор одноимённых городов → «Мои места», дата, рассылки → предупреждения → advice, по часам →
/air, /weekend, /compare, норма → рефакторинг на `core.py` + `handlers/` (PR #1) → Python 3.14 в Docker (#2)
→ исправления после тестирования (#3) → /settings: модели и источник воздуха (#4) → сумерки, точка росы,
/table (#5) → поля краткой сводки, Nominatim (#6) → /radar, /models, /review (#7) → сторож сервера (#8) →
heartbeat (#9) → повтор рассылок (#10) → OpenWeatherMap (#11) → «Среднее» (#12) → языки ru/uk/en (#13) →
английский README (#14). Аватар бота нарисован (`/mnt/project-files/bot-icon/`), установлен через BotFather.

## Что осталось / идеи
Отложено (смысл появится только при многих пользователях): inline-режим, работа в группах, SQLite вместо
JSON, общий кэш запросов, антифлуд, `/stats`. Дмитрий пользуется ботом и присылает пожелания/баги —
новые задачи берём из его отзывов.

## Известные проблемы
- Данные в JSON-файлах без блокировок между процессами — нормально для одного экземпляра, не запускай два.
- Состояние ожидания ввода (FSM) в памяти — после перезапуска бот забывает незаконченный вопрос.
- Первый расчёт нормы для нового места занимает несколько секунд (архив Open-Meteo).
- Пыльца — только Европа; WAQI почти бесполезен в Украине.
- Nominatim ограничен 1 запросом в секунду.
- Кратковременные сетевые сбои Telegram ночью (см. выше) — не баг.
