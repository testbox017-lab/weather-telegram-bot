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
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать и показать кнопки"),
            BotCommand(command="weather", description="Погода сейчас: /weather Город"),
            BotCommand(command="week", description="Прогноз на неделю: /week Город"),
            BotCommand(command="date", description="Погода на дату: /date 21.11 Город"),
            BotCommand(command="places", description="Мои места"),
            BotCommand(command="add", description="Добавить место: /add Город или /add 51.18 32.83"),
            BotCommand(command="del", description="Удалить место: /del номер или название"),
            BotCommand(command="subscribe", description="Рассылка погоды: /subscribe Город 3ч"),
            BotCommand(command="subs", description="Мои рассылки"),
            BotCommand(command="unsubscribe", description="Отключить рассылку: /unsubscribe номер|all"),
            BotCommand(command="alerts", description="Предупреждения: заморозок, гроза, ветер"),
            BotCommand(command="air", description="Качество воздуха и пыльца: /air Город"),
            BotCommand(command="weekend", description="Погода на выходные: /weekend Город"),
            BotCommand(command="table", description="3 дня таблицей: /table Город"),
            BotCommand(command="compare", description="Сравнить мои места"),
            BotCommand(command="radar", description="Радар осадков: /radar Город"),
            BotCommand(command="models", description="ECMWF, ICON и GFS на одном графике"),
            BotCommand(command="review", description="Итоги недели и точность прогноза"),
            BotCommand(command="settings", description="Источник погоды и качества воздуха"),
            BotCommand(command="ping", description="Проверить связь с сервером"),
            BotCommand(command="help", description="Справка"),
        ])
    except Exception:
        logging.exception("set_my_commands error")
    async with aiohttp.ClientSession() as session:
        core.client = WeatherClient(session)
        core.client.model_hook = lambda: core.prefs.current()["model"]
        tasks = [asyncio.create_task(scheduler(bot)), asyncio.create_task(alert_checker(bot)),
                 asyncio.create_task(extras.forecast_logger(bot))]
        try:
            await dp.start_polling(bot)
        finally:
            for task in tasks:
                task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
