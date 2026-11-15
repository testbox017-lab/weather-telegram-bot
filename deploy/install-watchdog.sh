#!/bin/bash
# Один раз на сервере (root): ставит сторожа и запускает его каждые 5 минут.
#   sudo bash /opt/weather-bot/deploy/install-watchdog.sh
# Как и деплой с бэкапом, скрипт копируется в /usr/local/bin: коммит в main сам его не поменяет.
set -euo pipefail
cd "$(dirname "$0")"
install -m 755 watchdog.sh /usr/local/bin/weather-bot-watchdog
cat > /etc/cron.d/weather-bot-watchdog <<'CRON'
*/5 * * * * root /usr/local/bin/weather-bot-watchdog >> /var/log/weather-bot-watchdog.log 2>&1
CRON
chmod 644 /etc/cron.d/weather-bot-watchdog
cat > /etc/logrotate.d/weather-bot-watchdog <<'ROT'
/var/log/weather-bot-watchdog.log {
    monthly
    rotate 3
    compress
    missingok
    notifempty
}
ROT
/usr/local/bin/weather-bot-watchdog --test
echo "ok: weather-bot-watchdog, cron каждые 5 минут"
