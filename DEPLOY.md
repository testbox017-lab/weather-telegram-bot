# Запуск бота на сервере 24/7 (Ubuntu VPS)

> ⚠️ **Важно: один токен — один запущенный бот.** Перед запуском на сервере остановите бота на Windows
> (`stop_bot.bat`). Если работают два экземпляра с одним токеном, Telegram отдаёт ошибку
> `TelegramConflictError` и сообщения теряются.

Подойдёт любой VPS с Ubuntu 22.04/24.04 (хватит 1 ядра и 512 МБ–1 ГБ памяти). Ниже два способа:
**A — Docker (рекомендуется)** и **B — venv + systemd**.

## Подготовка

Подключитесь к серверу (`ssh user@IP_сервера`) и установите git:

```bash
sudo apt update && sudo apt install -y git
```

Скачайте код (адрес репозитория — ваш):

```bash
sudo git clone https://github.com/<логин>/<репозиторий>.git /opt/weather-bot
sudo chown -R $USER:$USER /opt/weather-bot
cd /opt/weather-bot
```

### Файл .env с токеном

Токен **не хранится в репозитории** (файл `.env` в `.gitignore`). Создайте его прямо на сервере:

```bash
cd /opt/weather-bot
cp .env.example .env
nano .env          # впишите BOT_TOKEN=..., сохраните: Ctrl+O, Enter, выход: Ctrl+X
chmod 600 .env     # читать файл может только владелец
```

Не отправляйте токен в чаты, письма и коммиты. Если токен всё же «утёк» — выпустите новый у
[@BotFather](https://t.me/BotFather) командой `/revoke` и обновите `.env`.

## A. Docker (рекомендуется)

1. Установите Docker. Для Ubuntu 26.04 у Docker пока нет своего репозитория, поэтому ставим пакеты
   из Ubuntu (на 22.04/24.04 можно и так, и через `curl -fsSL https://get.docker.com | sudo sh`):
   ```bash
   sudo apt install -y docker.io docker-compose-v2
   sudo systemctl enable --now docker
   ```
2. Создайте папку для данных пользователей (последние места, «Мои места») — контейнер работает
   от пользователя с uid 1000:
   ```bash
   cd /opt/weather-bot
   mkdir -p data && sudo chown 1000:1000 data
   ```
3. Запустите:
   ```bash
   docker compose up -d --build
   ```
4. Проверьте логи (должно быть `Run polling for bot ...`):
   ```bash
   docker compose logs -f --tail 50     # выход: Ctrl+C
   ```

Бот перезапускается сам после сбоя и после перезагрузки сервера (`restart: unless-stopped`).

| Действие | Команда |
|---|---|
| Остановить | `docker compose stop` |
| Запустить снова | `docker compose start` |
| Статус | `docker compose ps` |
| **Обновить код** | `git pull && docker compose up -d --build` |

### Обновление с Windows без git

Если код копировался на сервер в `/opt/weather-bot` напрямую (без git), новую версию можно залить
из PowerShell в папке бота (`<SERVER_IP>` — адрес вашего сервера):

```powershell
tar -cf $env:TEMP\bot.tar --exclude __pycache__ *.py requirements.txt Dockerfile docker-compose.yml .dockerignore
scp $env:TEMP\bot.tar root@<SERVER_IP>:/tmp/bot.tar
ssh root@<SERVER_IP> "cd /opt/weather-bot && tar -xf /tmp/bot.tar && docker compose up -d --build"
```

`.env` и папка `data/` при этом не затрагиваются. Логи: `ssh root@<SERVER_IP> "cd /opt/weather-bot && docker compose logs --tail 50"`.

Сервер: на нём включены firewall `ufw` (открыт только SSH) и автоматические обновления безопасности
(`unattended-upgrades`). Иногда после обновлений нужна перезагрузка (`sudo reboot`) — бот поднимется сам.

## B. Без Docker: venv + systemd

1. Python и отдельный пользователь для бота:
   ```bash
   sudo apt install -y python3 python3-venv
   sudo useradd --system --home /opt/weather-bot --shell /usr/sbin/nologin weatherbot
   ```
2. Виртуальное окружение и зависимости:
   ```bash
   cd /opt/weather-bot
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   sudo chown -R weatherbot:weatherbot /opt/weather-bot
   ```
   (`.env` создайте, как описано выше, до `chown`.)
3. Служба systemd:
   ```bash
   sudo cp deploy/weather-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now weather-bot
   ```
4. Логи:
   ```bash
   sudo journalctl -u weather-bot -f     # выход: Ctrl+C
   ```

| Действие | Команда |
|---|---|
| Остановить / запустить | `sudo systemctl stop weather-bot` / `sudo systemctl start weather-bot` |
| Статус | `sudo systemctl status weather-bot` |
| **Обновить код** | `cd /opt/weather-bot && sudo -u weatherbot git pull && sudo -u weatherbot .venv/bin/pip install -r requirements.txt && sudo systemctl restart weather-bot` |

## Перенос данных пользователей с Windows (необязательно)

Чтобы бот на сервере помнил последние места и «Мои места», скопируйте файлы с Windows
(из папки бота) на сервер:

```bash
scp last_places.json saved_places.json user@IP_сервера:/opt/weather-bot/data/   # для Docker
```

Для способа B — в `/opt/weather-bot/` (или в папку из `DATA_DIR` в `.env`), затем
`sudo chown weatherbot:weatherbot` на эти файлы.
