FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# Непривилегированный пользователь и папка для данных пользователей бота
RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /data \
    && chown bot:bot /data
USER bot

VOLUME /data

CMD ["python", "bot.py"]
