#!/bin/bash
# Сторож сервера: раз в 5 минут (cron) проверяет бота и сервер и пишет владельцу в Telegram, если что-то
# сломалось, и ещё раз — когда починилось. Работает вне контейнера, поэтому сообщит, даже если бот упал.
#
# Проверки: контейнер не запущен или перезапускался; ошибки в логах бота; бэкап старше 26 ч;
# диск заполнен больше чем на 80 %; Open-Meteo не отвечает 3 проверки подряд; сервер перезагружался.
#
# Устанавливается в /usr/local/bin/weather-bot-watchdog (deploy/install-watchdog.sh).
# Токен — BOT_TOKEN из /opt/weather-bot/.env. Кому писать — ADMIN_CHAT_ID из .env, а если его нет,
# единственный пользователь бота из data/ (бот личный). Ночью (23–7 по Киеву) сообщения приходят без звука.
#   weather-bot-watchdog          — обычная проверка
#   weather-bot-watchdog --test   — прислать проверочное сообщение и показать, что сейчас не так
set -uo pipefail

APP=${APP:-/opt/weather-bot}
STATE=${STATE:-/var/lib/weather-bot-watchdog}
BACKUPS=${BACKUPS:-/var/backups/weather-bot}
CONTAINER=${CONTAINER:-weather-bot}
DEPLOY_LOCK=${DEPLOY_LOCK:-/tmp/weather-bot-deploy.lock}
BOOT_ID_FILE=${BOOT_ID_FILE:-/proc/sys/kernel/random/boot_id}
DISK_PATH=${DISK_PATH:-/}
DISK_LIMIT=${DISK_LIMIT:-80}          # %
BACKUP_MAX_HOURS=${BACKUP_MAX_HOURS:-26}
OM_FAILS=${OM_FAILS:-3}               # подряд неудачных проверок Open-Meteo до тревоги
REMIND_HOURS=${REMIND_HOURS:-12}      # напоминать о неисправленном раз в столько часов
ERRORS_EVERY_MIN=${ERRORS_EVERY_MIN:-60}  # об ошибках в логах — не чаще раза в час
OM_URL=${OM_URL:-"https://api.open-meteo.com/v1/forecast?latitude=51.18&longitude=32.83&current=temperature_2m"}
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
NOW=${NOW:-$(date +%s)}
# шум aiogram при коротких обрывах связи с Telegram: он сам переподключается
LOG_IGNORE=${LOG_IGNORE:-'Failed to fetch updates|Sleep for [0-9.]+ seconds and try again|Connection lost'}

mkdir -p "$STATE/problems"
chmod 700 "$STATE"
TEST=0
[ "${1:-}" = "--test" ] && TEST=1

env_value() {  # значение KEY из .env без кавычек; сам файл никуда не выводится
  [ -r "$APP/.env" ] || return 0
  sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$APP/.env" | tail -n 1 | tr -d '\r"'"'"
}

TOKEN=$(env_value BOT_TOKEN)
CHAT=$(env_value ADMIN_CHAT_ID)
if [ -z "$CHAT" ]; then  # личный бот: единственный пользователь из файлов данных
  CHAT=$(python3 - "$APP/data" <<'PY' 2>/dev/null
import json, sys
from pathlib import Path
ids = set()
for name in ("saved_places.json", "last_places.json", "subscriptions.json", "alerts.json", "prefs.json"):
    try:
        ids |= {k for k in json.loads((Path(sys.argv[1]) / name).read_text(encoding="utf-8")) if k.lstrip("-").isdigit()}
    except Exception:
        pass
print(ids.pop() if len(ids) == 1 else "")
PY
)
fi

log() { echo "$(date -Is) $*"; }

send() {  # send "текст" → 0, если Telegram принял
  if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
    log "нет BOT_TOKEN или ADMIN_CHAT_ID — сообщение не отправлено: $1"
    return 1
  fi
  local hour silent=false
  hour=$(TZ=Europe/Kyiv date -d "@$NOW" +%H)
  { [ "$hour" -ge 23 ] || [ "$hour" -lt 7 ]; } && silent=true
  "$CURL" -fsS -m 20 -o /dev/null "https://api.telegram.org/bot$TOKEN/sendMessage" \
    --data-urlencode "chat_id=$CHAT" --data-urlencode "text=$1" \
    --data-urlencode "disable_notification=$silent" 2>/dev/null
}

# Проблема, которая держится, пока её не исправят: тревога один раз (и напоминание раз в REMIND_HOURS),
# потом «снова в порядке».
problem() {  # problem ключ "текст"
  local f="$STATE/problems/$1" since
  FOUND="$FOUND $1"
  if [ -f "$f" ]; then
    since=$(head -n 1 "$f")
    if [ $((NOW - $(sed -n 2p "$f"))) -ge $((REMIND_HOURS * 3600)) ]; then
      send "🔴 Всё ещё: $2 (с $(TZ=Europe/Kyiv date -d "@$since" '+%d.%m %H:%M'))" && printf '%s\n%s\n' "$since" "$NOW" > "$f"
    fi
    return
  fi
  if send "🔴 Погодный бот: $2"; then
    printf '%s\n%s\n%s\n' "$NOW" "$NOW" "$2" > "$f"
    log "тревога $1: $2"
  fi
}

resolve_all() {  # всё, что было в problems/, но не нашлось сейчас, — починилось
  local f k
  for f in "$STATE"/problems/*; do
    [ -f "$f" ] || continue
    k=$(basename "$f")
    case " $FOUND " in *" $k "*) continue ;; esac
    if send "🟢 Снова в порядке: $(sed -n 3p "$f")"; then
      rm -f "$f"
      log "в порядке $k"
    fi
  done
}

FOUND=""
LAST=$(cat "$STATE/last_run" 2>/dev/null || echo $((NOW - 300)))

# --- перезагрузка ---
boot=$(cat "$BOOT_ID_FILE" 2>/dev/null || true)
if [ -n "$boot" ] && [ -f "$STATE/boot_id" ] && [ "$boot" != "$(cat "$STATE/boot_id")" ]; then
  send "🔄 Сервер перезагружался, работает с $(uptime -s 2>/dev/null || echo '?') (UTC). Обычно это плановая перезагрузка после обновлений в 04:00." \
    && log "перезагрузка"
fi
[ -n "$boot" ] && echo "$boot" > "$STATE/boot_id"

# --- контейнер (во время деплоя не проверяем: он как раз перезапускается) ---
deploying=0
if [ -e "$DEPLOY_LOCK" ] && command -v flock >/dev/null; then
  exec 9>>"$DEPLOY_LOCK"
  flock -n 9 || deploying=1
  exec 9>&-
fi
if [ "$deploying" = 0 ]; then
  info=$("$DOCKER" inspect -f '{{.State.Status}} {{.RestartCount}} {{.State.StartedAt}}' "$CONTAINER" 2>/dev/null)
  status=${info%% *}
  rest=${info#* }
  restarts=${rest%% *}
  started=${rest#* }
  if [ -z "$info" ]; then
    problem container "контейнер $CONTAINER не найден"
  elif [ "$status" != running ]; then
    problem container "контейнер не работает (состояние: $status)"
  else
    prev=$(cat "$STATE/container" 2>/dev/null || true)
    # RestartCount растёт, когда Docker поднимает упавший контейнер; деплой создаёт новый контейнер (счётчик 0)
    if [ -n "$prev" ] && [ "$restarts" -gt "${prev#* }" ] 2>/dev/null; then
      send "⚠️ Бот упал и перезапустился (перезапусков с последнего деплоя: $restarts). Сейчас работает." \
        && log "перезапуск $restarts"
    fi
    echo "$started $restarts" > "$STATE/container"
  fi

  # --- ошибки в логах с прошлой проверки ---
  if [ "${status:-}" = running ]; then
    errs=$("$DOCKER" logs --since "$LAST" "$CONTAINER" 2>&1 | grep -E 'ERROR|CRITICAL|Traceback' | grep -Ev "$LOG_IGNORE" || true)
    if [ -n "$errs" ]; then
      n=$(printf '%s\n' "$errs" | wc -l)
      total=$(( $(cat "$STATE/errors_pending" 2>/dev/null || echo 0) + n ))
      printf '%s\n' "$errs" | tail -n 3 | cut -c1-200 > "$STATE/errors_sample"
      echo "$total" > "$STATE/errors_pending"
    fi
    total=$(cat "$STATE/errors_pending" 2>/dev/null || echo 0)
    sent_at=$(cat "$STATE/errors_sent" 2>/dev/null || echo 0)
    if [ "$total" -gt 0 ] && [ $((NOW - sent_at)) -ge $((ERRORS_EVERY_MIN * 60)) ]; then
      if send "⚠️ В логах бота ошибки: $total. Последние:
$(cat "$STATE/errors_sample")
Подробнее: docker compose logs --tail 100 (в /opt/weather-bot)"; then
        echo 0 > "$STATE/errors_pending"
        echo "$NOW" > "$STATE/errors_sent"
        log "ошибки в логах: $total"
      fi
    fi
  fi
fi

# --- бэкап ---
newest=$(ls -1t "$BACKUPS"/weather-bot-*.tar.gz 2>/dev/null | head -n 1)
if [ -z "$newest" ]; then
  problem backup "нет ни одного бэкапа в $BACKUPS"
else
  age=$(( (NOW - $(stat -c %Y "$newest")) / 3600 ))
  [ "$age" -ge "$BACKUP_MAX_HOURS" ] && problem backup "последний бэкап сделан $age ч назад (должен быть каждую ночь в 03:30 UTC)"
fi

# --- диск ---
used=$(df --output=pcent "$DISK_PATH" 2>/dev/null | tail -n 1 | tr -dc '0-9')
[ -n "$used" ] && [ "$used" -gt "$DISK_LIMIT" ] && problem disk "диск заполнен на $used % (порог $DISK_LIMIT %)"

# --- Open-Meteo ---
if "$CURL" -fsS -m 15 -o /dev/null "$OM_URL" 2>/dev/null; then
  echo 0 > "$STATE/om_fails"
else
  fails=$(( $(cat "$STATE/om_fails" 2>/dev/null || echo 0) + 1 ))
  echo "$fails" > "$STATE/om_fails"
fi
fails=$(cat "$STATE/om_fails")
[ "$fails" -ge "$OM_FAILS" ] && problem openmeteo "Open-Meteo не отвечает уже $fails проверки подряд (≈$((fails * 5)) мин) — прогнозы не приходят"

resolve_all
echo "$NOW" > "$STATE/last_run"

if [ "$TEST" = 1 ]; then
  if send "✅ Сторож сервера работает: проверяет бота каждые 5 минут и напишет сюда, если что-то сломается."; then
    echo "проверочное сообщение отправлено"
  else
    echo "не удалось отправить проверочное сообщение" >&2
    exit 1
  fi
  echo "сейчас не в порядке:${FOUND:- ничего}"
fi
exit 0
