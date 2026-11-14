#!/bin/bash
# Один раз на сервере (root): ставит скрипты деплоя и бэкапа, включает ежедневный бэкап.
#   sudo bash /opt/weather-bot/deploy/install-server.sh
# Скрипты копируются в /usr/local/bin, а не запускаются из репозитория: так коммит в main
# не может сам поменять то, что выполняется от root.
set -euo pipefail
cd "$(dirname "$0")"
install -m 755 deploy.sh /usr/local/bin/weather-bot-deploy
install -m 755 backup.sh /usr/local/bin/weather-bot-backup
cat > /etc/cron.d/weather-bot-backup <<'CRON'
30 3 * * * root /usr/local/bin/weather-bot-backup >> /var/log/weather-bot-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/weather-bot-backup
/usr/local/bin/weather-bot-backup
echo "ok: weather-bot-deploy, weather-bot-backup, cron 03:30"
