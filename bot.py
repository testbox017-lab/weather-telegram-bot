"""Погодный Telegram-бот. Запуск: python bot.py (токен в .env)

Обработчики разложены по роутерам в handlers/: places, dates, subs, settings и weather;
общее (хранилища, клиент Open-Meteo, кнопки, состояния ожидания ввода) — в core.py.
"""
import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import core
import health
from core import CurrentUserMiddleware, ResetInputMiddleware
from handlers import dates, extras, places, settings, subs, weather
from handlers.settings import alert_checker
from handlers.subs import scheduler
from weather import WeatherClient

ROUTERS = (places.router, dates.router, subs.router, settings.router, extras.router,
           weather.router)  # weather последним: его обработчик текста ловит всё остальное


def build_dispatcher() -> Dispatcher:
    """Диспетчер с роутерами и ожиданием ввода в памяти (как раньше словарь waiting:
    после перезапуска бот забывает, что спрашивал)."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(CurrentUserMiddleware())
    dp.message.middleware(ResetInputMiddleware())
    dp.include_routers(*ROUTERS)
    return dp


async def main():
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Не найден BOT_TOKEN: создайте файл .env рядом с bot.py со строкой BOT_TOKEN=ваш_токен")
    bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = build_dispatcher()
    try:
        await bot.set_my_commands(core.bot_commands())  # по-русски; другой язык из /settings ставит свои
        # подписи для своего чата (handlers.settings.on_language_changed) — их Telegram помнит сам
    except Exception:
        logging.exception("set_my_commands error")
    async with aiohttp.ClientSession() as session:
        core.client = WeatherClient(session)
        core.client.model_hook = lambda: core.prefs.current()["model"]
        tasks = [asyncio.create_task(scheduler(bot)), asyncio.create_task(alert_checker(bot)),
                 asyncio.create_task(extras.forecast_logger(bot)),
                 asyncio.create_task(health.heartbeat_loop(bot, core.DATA_DIR / health.HEARTBEAT_FILE))]
        try:
            await dp.start_polling(bot)
        finally:
            for task in tasks:
                task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
