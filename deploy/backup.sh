#!/bin/bash
# Ежедневная копия данных пользователей бота (места, рассылки, предупреждения).
# Устанавливается в /usr/local/bin/weather-bot-backup, запускается cron'ом в 03:30.
# Хранятся последние 14 копий в /var/backups/weather-bot, latest.tar.gz — самая свежая.
set -euo pipefail
SRC=/opt/weather-bot/data
DST=/var/backups/weather-bot
KEEP=14
mkdir -p "$DST"
chmod 700 "$DST"
file="$DST/weather-bot-$(date +%Y-%m-%d_%H%M).tar.gz"
tar -czf "$file" -C "$SRC" .
cp -f "$file" "$DST/latest.tar.gz"
ls -1t "$DST"/weather-bot-*.tar.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "$(date -Is) backup $(du -h "$file" | cut -f1) $file"
