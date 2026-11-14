"""Проверка без Telegram: тот же код, что выполняет бот при получении геолокации.
Запуск: python check_location.py"""
import asyncio

import aiohttp

from weather import Place, WeatherClient


async def main():
    async with aiohttp.ClientSession() as s:
        c = WeatherClient(s)
        # Геолокация: Бахмач, Нежинский район, Черниговская область
        print(await c.forecast(Place("Ваше местоположение", 51.1808, 32.8239), 1))
        print("\n---\n")
        # Поиск по названию, как если написать боту «Бахмач»
        place = await c.find_city("Бахмач")
        print("Найдено:", place)
        if place:
            print(await c.forecast(place, 7))


asyncio.run(main())
