FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY handlers/ ./handlers/

# Версия для /ping: GIT_COMMIT=$(git rev-parse --short HEAD) docker compose up -d --build
ARG GIT_COMMIT=unknown
ARG GIT_DATE=
ENV GIT_COMMIT=$GIT_COMMIT GIT_DATE=$GIT_DATE

# Непривилегированный пользователь и папка для данных пользователей бота
RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /data \
    && chown bot:bot /data
USER bot

VOLUME /data

# Бот раз в минуту пишет /data/heartbeat.json; если метка устарела или планировщик рассылок завис,
# контейнер становится unhealthy (это видит мониторинг сервера). Подробности: health.py
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=3 CMD ["python", "healthcheck.py"]

CMD ["python", "bot.py"]
