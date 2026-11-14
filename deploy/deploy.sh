#!/bin/bash
# Обновление бота на сервере: git pull + пересборка контейнера + проверка, что он запустился.
# Устанавливается в /usr/local/bin/weather-bot-deploy (deploy/install-server.sh). Его запускает
# GitHub Actions по отдельному ключу, которому в authorized_keys разрешена только эта команда.
set -euo pipefail
APP=/opt/weather-bot
exec 9>/tmp/weather-bot-deploy.lock
flock -w 600 9          # два деплоя подряд не мешают друг другу
cd "$APP"
echo "== $(date -Is) деплой, было: $(git rev-parse --short HEAD)"
git pull --ff-only --quiet origin main
export GIT_COMMIT GIT_DATE
GIT_COMMIT=$(git rev-parse --short HEAD)
GIT_DATE=$(git log -1 --format=%cd --date=format:%d.%m.%Y)
echo "   стало: $GIT_COMMIT"
docker compose up -d --build --quiet-pull 2>&1 | tail -n 5
sleep 20
state=$(docker inspect -f '{{.State.Status}} restarts={{.RestartCount}}' weather-bot)
echo "   контейнер: $state"
docker compose logs --tail 15 weather-bot
case "$state" in
  "running restarts=0") echo "== готово" ;;
  *) echo "== контейнер не в порядке" >&2; exit 1 ;;
esac
