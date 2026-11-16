"""Переводы: русская строка из кода → (украинский, английский). Подробности — в i18n.py.

Новая строка в коде (_("…") или N_("…")) — добавьте её сюда; tests/test_i18n.py подскажет, чего не хватает
(или: python tools/i18n_keys.py --missing en). Подстановки {…} в переводе — те же, что в ключе.
"""

T = {
    # ---------- Дни недели (i18n.WEEKDAYS) ----------
    "Пн": ("Пн", "Mon"),
    "Вт": ("Вт", "Tue"),
    "Ср": ("Ср", "Wed"),
    "Чт": ("Чт", "Thu"),
    "Пт": ("Пт", "Fri"),
    "Сб": ("Сб", "Sat"),
    "Вс": ("Нд", "Sun"),
    "Суббота": ("Субота", "Saturday"),
    "Воскресенье": ("Неділя", "Sunday"),

    # ---------- Погода словами (weather.WMO) ----------
    "Ясно": ("Ясно", "Clear"),
    "Преимущественно ясно": ("Переважно ясно", "Mostly clear"),
    "Переменная облачность": ("Мінлива хмарність", "Partly cloudy"),
    "Пасмурно": ("Похмуро", "Overcast"),
    "Туман": ("Туман", "Fog"),
    "Изморозь": ("Паморозь", "Rime fog"),
    "Слабая морось": ("Слабка мряка", "Light drizzle"),
    "Морось": ("Мряка", "Drizzle"),
    "Сильная морось": ("Сильна мряка", "Heavy drizzle"),
    "Ледяная морось": ("Крижана мряка", "Freezing drizzle"),
    "Сильная ледяная морось": ("Сильна крижана мряка", "Heavy freezing drizzle"),
    "Небольшой дождь": ("Невеликий дощ", "Light rain"),
    "Дождь": ("Дощ", "Rain"),
    "Сильный дождь": ("Сильний дощ", "Heavy rain"),
    "Ледяной дождь": ("Крижаний дощ", "Freezing rain"),
    "Сильный ледяной дождь": ("Сильний крижаний дощ", "Heavy freezing rain"),
    "Небольшой снег": ("Невеликий сніг", "Light snow"),
    "Снег": ("Сніг", "Snow"),
    "Сильный снег": ("Сильний сніг", "Heavy snow"),
    "Снежные зёрна": ("Снігова крупа", "Snow grains"),
    "Небольшой ливень": ("Невелика злива", "Light showers"),
    "Ливень": ("Злива", "Showers"),
    "Сильный ливень": ("Сильна злива", "Heavy showers"),
    "Снегопад": ("Снігопад", "Snow showers"),
    "Сильный снегопад": ("Сильний снігопад", "Heavy snow showers"),
    "Гроза": ("Гроза", "Thunderstorm"),
    "Гроза с градом": ("Гроза з градом", "Thunderstorm with hail"),
    "Сильная гроза с градом": ("Сильна гроза з градом", "Severe thunderstorm with hail"),
    "Неизвестно": ("Невідомо", "Unknown"),

    # ---------- Прогноз (weather.py) ----------
    "📅 <b>Погода на {wd} {day:%d.%m.%Y}</b> — {name}": ("📅 <b>Погода на {wd} {day:%d.%m.%Y}</b> — {name}",
                                                        "📅 <b>Weather for {wd} {day:%d.%m.%Y}</b> — {name}"),
    "<i>фактические данные (архив)</i>": ("<i>фактичні дані (архів)</i>", "<i>observed data (archive)</i>"),
    "Нет данных за эту дату 🤷": ("Немає даних за цю дату 🤷", "No data for this date 🤷"),
    "☔️ Осадки: {rain:.1f} мм": ("☔️ Опади: {rain:.1f} мм", "☔️ Precipitation: {rain:.1f} mm"),
    ", вероятность {prob}%": (", ймовірність {prob}%", ", chance {prob}%"),
    "💨 Ветер до {wind:.1f} м/с": ("💨 Вітер до {wind:.1f} м/с", "💨 Wind up to {wind:.1f} m/s"),
    ", порывы до {gust:.1f} м/с": (", пориви до {gust:.1f} м/с", ", gusts up to {gust:.1f} m/s"),
    "💧 Влажность: {hum}%{rng}": ("💧 Вологість: {hum}%{rng}", "💧 Humidity: {hum}%{rng}"),
    "северный": ("північний", "northerly"),
    "северо-восточный": ("північно-східний", "northeasterly"),
    "восточный": ("східний", "easterly"),
    "юго-восточный": ("південно-східний", "southeasterly"),
    "южный": ("південний", "southerly"),
    "юго-западный": ("південно-західний", "southwesterly"),
    "западный": ("західний", "westerly"),
    "северо-западный": ("північно-західний", "northwesterly"),
    "низкий": ("низький", "low"),
    "умеренный, нужен крем SPF 30": ("помірний, потрібен крем SPF 30", "moderate, use SPF 30 sunscreen"),
    "высокий, крем SPF 50 и головной убор": ("високий, крем SPF 50 і головний убір",
                                             "high, SPF 50 sunscreen and a hat"),
    "очень высокий, избегайте солнца в полдень": ("дуже високий, уникайте сонця опівдні",
                                                  "very high, avoid the midday sun"),
    "экстремальный, лучше не выходить на солнце": ("екстремальний, краще не виходити на сонце",
                                                   "extreme, better stay out of the sun"),
    "🕶 УФ-индекс до {uv} — {level}": ("🕶 УФ-індекс до {uv} — {level}", "🕶 UV index up to {uv} — {level}"),
    "{km:.1f} км": ("{km:.1f} км", "{km:.1f} km"),
    "{m} м": ("{m} м", "{m} m"),
    "👁 Видимость {shown}": ("👁 Видимість {shown}", "👁 Visibility {shown}"),
    " — туман": (" — туман", " — fog"),
    "☔️ Снег идёт и не прекратится ближайшие {n} ч": ("☔️ Іде сніг і не припиниться найближчі {n} год",
                                                     "☔️ Snowing, won't stop in the next {n} h"),
    "☔️ Дождь идёт и не прекратится ближайшие {n} ч": ("☔️ Іде дощ і не припиниться найближчі {n} год",
                                                      "☔️ Raining, won't stop in the next {n} h"),
    "☔️ Снег идёт, закончится около {t}": ("☔️ Іде сніг, закінчиться близько {t}",
                                           "☔️ Snowing, should stop around {t}"),
    "☔️ Дождь идёт, закончится около {t}": ("☔️ Іде дощ, закінчиться близько {t}",
                                            "☔️ Raining, should stop around {t}"),
    "🌂 Без осадков ближайшие {n} ч": ("🌂 Без опадів найближчі {n} год", "🌂 No precipitation in the next {n} h"),
    " (вероятность {p}%)": (" (ймовірність {p}%)", " (chance {p}%)"),
    "☔️ Снег начнётся около {t}{chance}": ("☔️ Сніг почнеться близько {t}{chance}",
                                           "☔️ Snow will start around {t}{chance}"),
    "☔️ Дождь начнётся около {t}{chance}": ("☔️ Дощ почнеться близько {t}{chance}",
                                            "☔️ Rain will start around {t}{chance}"),
    "↔️ Так же, как вчера в это время": ("↔️ Так само, як учора о цій порі", "↔️ Same as yesterday at this time"),
    "🔺 На {n}° теплее, чем вчера в это время": ("🔺 На {n}° тепліше, ніж учора о цій порі",
                                                 "🔺 {n}° warmer than yesterday at this time"),
    "🔻 На {n}° холоднее, чем вчера в это время": ("🔻 На {n}° холодніше, ніж учора о цій порі",
                                                   "🔻 {n}° colder than yesterday at this time"),
    "🌡 {t}°C (ощущается как {feels}°C)": ("🌡 {t}°C (відчувається як {feels}°C)", "🌡 {t}°C (feels like {feels}°C)"),
    "💧 Влажность: {hum}%": ("💧 Вологість: {hum}%", "💧 Humidity: {hum}%"),
    ", точка росы {dew}°": (", точка роси {dew}°", ", dew point {dew}°"),
    "💨 Ветер: {wind:.1f} м/с": ("💨 Вітер: {wind:.1f} м/с", "💨 Wind: {wind:.1f} m/s"),
    ", порывы до {gust:.0f} м/с": (", пориви до {gust:.0f} м/с", ", gusts up to {gust:.0f} m/s"),
    "🧭 Давление: {p} мм рт. ст.": ("🧭 Тиск: {p} мм рт. ст.", "🧭 Pressure: {p} mmHg"),
    "☁️ Облачность: {c}%": ("☁️ Хмарність: {c}%", "☁️ Cloud cover: {c}%"),
    "Сегодня: {lo}…{hi}°C, вероятность осадков {p}%": ("Сьогодні: {lo}…{hi}°C, ймовірність опадів {p}%",
                                                         "Today: {lo}…{hi}°C, chance of precipitation {p}%"),
    "<b>Прогноз на {n} дн.:</b>": ("<b>Прогноз на {n} дн.:</b>", "<b>{n}-day forecast:</b>"),
    ", 💨 {w} м/с": (", 💨 {w} м/с", ", 💨 {w} m/s"),
    "Погода и температура": ("Погода і температура", "Weather and temperature"),
    "Ощущается": ("Відчувається", "Feels like"),
    "Ветер": ("Вітер", "Wind"),
    "Влажность": ("Вологість", "Humidity"),
    "Давление": ("Тиск", "Pressure"),
    "Осадки на 12 ч": ("Опади на 12 год", "Precipitation, 12 h"),
    "Сегодня мин…макс": ("Сьогодні мін…макс", "Today min…max"),
    "Что надеть": ("Що вдягнути", "What to wear"),
    " (ощущается {f}°)": (" (відчувається {f}°)", " (feels like {f}°)"),
    "ощущается {f}°": ("відчувається {f}°", "feels like {f}°"),
    "💨 {w:.0f} м/с": ("💨 {w:.0f} м/с", "💨 {w:.0f} m/s"),
    "🧭 {p} мм": ("🧭 {p} мм", "🧭 {p} mmHg"),
    "Сегодня {lo}…{hi}°C": ("Сьогодні {lo}…{hi}°C", "Today {lo}…{hi}°C"),
    "Нет почасовых данных 🤷": ("Немає погодинних даних 🤷", "No hourly data 🤷"),
    "⏱ <b>{name}</b> — по часам": ("⏱ <b>{name}</b> — по годинах", "⏱ <b>{name}</b> — hourly"),
    " {mm:.1f} мм": (" {mm:.1f} мм", " {mm:.1f} mm"),

    # ---------- Что надеть, точка росы (advice.py) ----------
    "пуховик, шапка, шарф и варежки": ("пуховик, шапка, шарф і рукавиці", "down jacket, hat, scarf and mittens"),
    "зимняя куртка, шапка и перчатки": ("зимова куртка, шапка і рукавички", "winter jacket, hat and gloves"),
    "тёплая куртка и шапка": ("тепла куртка і шапка", "warm jacket and a hat"),
    "куртка или пальто": ("куртка або пальто", "jacket or coat"),
    "лёгкая куртка или свитер": ("легка куртка або светр", "light jacket or sweater"),
    "футболка, на вечер кофта": ("футболка, на вечір кофта", "T-shirt, a sweater for the evening"),
    "лёгкая одежда, пейте больше воды": ("легкий одяг, пийте більше води", "light clothes, drink plenty of water"),
    "непромокаемая обувь": ("непромокальне взуття", "waterproof shoes"),
    "капюшон или дождевик — зонт вывернет ветром": ("капюшон або дощовик — парасольку виверне вітром",
                                                    "a hood or raincoat — wind will wreck an umbrella"),
    "зонт": ("парасолька", "umbrella"),
    "одежда от ветра": ("одяг від вітру", "windproof clothes"),
    "крем от солнца и очки": ("крем від сонця й окуляри", "sunscreen and sunglasses"),
    "🥵 Очень душно: точка росы {d}°": ("🥵 Дуже задушливо: точка роси {d}°", "🥵 Very muggy: dew point {d}°"),
    "😓 Душно: точка росы {d}°": ("😓 Задушливо: точка роси {d}°", "😓 Muggy: dew point {d}°"),
    "🌫 Воздух почти насыщен влагой — возможен туман": ("🌫 Повітря майже насичене вологою — можливий туман",
                                                        "🌫 The air is nearly saturated — fog is possible"),
    "🧊 Около нуля и влажно — возможен гололёд, осторожно на дорогах и тротуарах": (
        "🧊 Близько нуля й волого — можлива ожеледиця, обережно на дорогах і тротуарах",
        "🧊 Near freezing and damp — ice is possible, take care on roads and sidewalks"),
}

T.update({
    # ---------- Воздух (air.py) ----------
    "берёза": ("береза", "birch"),
    "ольха": ("вільха", "alder"),
    "злаки": ("злаки", "grasses"),
    "полынь": ("полин", "mugwort"),
    "амброзия": ("амброзія", "ragweed"),
    "олива": ("олива", "olive"),
    "хороший": ("добра", "good"),
    "приемлемый": ("прийнятна", "fair"),
    "умеренный": ("помірна", "moderate"),
    "плохой": ("погана", "poor"),
    "очень плохой": ("дуже погана", "very poor"),
    "крайне плохой": ("вкрай погана", "extremely poor"),
    "Чувствительным людям лучше сократить долгие нагрузки на улице.": (
        "Чутливим людям краще скоротити тривалі навантаження на вулиці.",
        "Sensitive people should cut down on long outdoor exertion."),
    "Лучше сократить пробежки и долгие прогулки, проветривать ненадолго.": (
        "Краще скоротити пробіжки й довгі прогулянки, провітрювати ненадовго.",
        "Better cut down on runs and long walks, air rooms only briefly."),
    "Лучше остаться дома и закрыть окна; на улице — без нагрузок.": (
        "Краще залишитися вдома й зачинити вікна; на вулиці — без навантажень.",
        "Better stay at home with windows closed; no exertion outdoors."),
    "низкая": ("низька", "low"),
    "средняя": ("середня", "medium"),
    "высокая": ("висока", "high"),
    "очень высокая": ("дуже висока", "very high"),
    "около {t}": ("близько {t}", "around {t}"),
    "завтра около {t}": ("завтра близько {t}", "tomorrow around {t}"),
    "🌫 <b>Воздух — {name}</b>": ("🌫 <b>Повітря — {name}</b>", "🌫 <b>Air — {name}</b>"),
    "Нет данных о качестве воздуха для этого места 🤷": ("Немає даних про якість повітря для цього місця 🤷",
                                                         "No air quality data for this place 🤷"),
    "{emoji} Качество воздуха: <b>{word}</b> (индекс EAQI {aqi})": (
        "{emoji} Якість повітря: <b>{word}</b> (індекс EAQI {aqi})",
        "{emoji} Air quality: <b>{word}</b> (EAQI {aqi})"),
    " мкг/м³": (" мкг/м³", " µg/m³"),
    "⏳ В ближайшие сутки ухудшится до «{w}» {e} {when}": ("⏳ Протягом доби погіршиться до «{w}» {e} {when}",
                                                          "⏳ Will worsen to “{w}” {e} {when}"),
    "🌼 Пыльца: ": ("🌼 Пилок: ", "🌼 Pollen: "),
    "🌼 Пыльцы в воздухе почти нет": ("🌼 Пилку в повітрі майже немає", "🌼 Almost no pollen in the air"),
    "🌼 Прогноз пыльцы доступен только для Европы": ("🌼 Прогноз пилку доступний лише для Європи",
                                                     "🌼 Pollen forecast is available for Europe only"),
    "вредный для чувствительных": ("шкідлива для чутливих", "unhealthy for sensitive groups"),
    "вредный": ("шкідлива", "unhealthy"),
    "очень вредный": ("дуже шкідлива", "very unhealthy"),
    "опасный": ("небезпечна", "hazardous"),
    "станция без названия": ("станція без назви", "unnamed station"),
    ": ближайшая — {station}, {km:.0f} км": (": найближча — {station}, {km:.0f} км",
                                            ": the nearest is {station}, {km:.0f} km"),
    "📡 Станций WAQI в пределах {r} км нет{where}. Источник можно сменить в /settings.": (
        "📡 Станцій WAQI в межах {r} км немає{where}. Джерело можна змінити в /settings.",
        "📡 No WAQI stations within {r} km{where}. You can change the source in /settings."),
    "📡 Станция {station} ({km:.1f} км) сейчас не передаёт данные 🤷": (
        "📡 Станція {station} ({km:.1f} км) зараз не передає даних 🤷",
        "📡 Station {station} ({km:.1f} km) isn't reporting right now 🤷"),
    ", измерено {d}.{m} {t}": (", виміряно {d}.{m} {t}", ", measured {d}.{m} {t}"),
    "📡 Станция: {station}, {km:.1f} км{stamp}": ("📡 Станція: {station}, {km:.1f} км{stamp}",
                                                 "📡 Station: {station}, {km:.1f} km{stamp}"),
    "{emoji} Качество воздуха: <b>{word}</b> (индекс US AQI {aqi})": (
        "{emoji} Якість повітря: <b>{word}</b> (індекс US AQI {aqi})",
        "{emoji} Air quality: <b>{word}</b> (US AQI {aqi})"),
    "🔬 Индексы: ": ("🔬 Індекси: ", "🔬 Indices: "),
    "<i>Данные: World Air Quality Index Project (aqicn.org)</i>": (
        "<i>Дані: World Air Quality Index Project (aqicn.org)</i>",
        "<i>Data: World Air Quality Index Project (aqicn.org)</i>"),

    # ---------- Предупреждения (alerts.py) ----------
    "❄️ Заморозок": ("❄️ Заморозок", "❄️ Frost"),
    "☔️ Осадки через 1–2 ч": ("☔️ Опади за 1–2 год", "☔️ Precipitation in 1–2 h"),
    "⛈ Гроза": ("⛈ Гроза", "⛈ Thunderstorm"),
    "💨 Ветер от 15 м/с": ("💨 Вітер від 15 м/с", "💨 Wind from 15 m/s"),
    "🔥 Жара от +30°": ("🔥 Спека від +30°", "🔥 Heat from +30°"),
    "🥶 Мороз от −20°": ("🥶 Мороз від −20°", "🥶 Cold from −20°"),
    "🌡 Перепад от 8°": ("🌡 Перепад від 8°", "🌡 Swing from 8°"),
    "❄️ Заморозок: до {t}°C около {at}": ("❄️ Заморозок: до {t}°C близько {at}", "❄️ Frost: down to {t}°C around {at}"),
    "🌨 Снег начнётся около {at}{prob}": ("🌨 Сніг почнеться близько {at}{prob}", "🌨 Snow will start around {at}{prob}"),
    "☔️ Дождь начнётся около {at}{prob}": ("☔️ Дощ почнеться близько {at}{prob}",
                                           "☔️ Rain will start around {at}{prob}"),
    "⛈ Гроза около {at}": ("⛈ Гроза близько {at}", "⛈ Thunderstorm around {at}"),
    "💨 Порывы ветра до {g} м/с около {at}": ("💨 Пориви вітру до {g} м/с близько {at}",
                                             "💨 Wind gusts up to {g} m/s around {at}"),
    "🔥 Жара до {t}°C около {at}": ("🔥 Спека до {t}°C близько {at}", "🔥 Heat up to {t}°C around {at}"),
    "🥶 Мороз до {t}°C около {at}": ("🥶 Мороз до {t}°C близько {at}", "🥶 Cold down to {t}°C around {at}"),
    "🌡 Завтра на {n}° теплее: днём до {t}°C": ("🌡 Завтра на {n}° тепліше: вдень до {t}°C",
                                               "🌡 Tomorrow {n}° warmer: up to {t}°C in the daytime"),
    "🌡 Завтра на {n}° холоднее: днём до {t}°C": ("🌡 Завтра на {n}° холодніше: вдень до {t}°C",
                                                 "🌡 Tomorrow {n}° colder: up to {t}°C in the daytime"),

    # ---------- Солнце и луна (astro.py) ----------
    "Новолуние": ("Новий місяць", "New moon"),
    "Растущий серп": ("Молодий місяць", "Waxing crescent"),
    "Первая четверть": ("Перша чверть", "First quarter"),
    "Растущая луна": ("Місяць росте", "Waxing gibbous"),
    "Полнолуние": ("Повня", "Full moon"),
    "Убывающая луна": ("Місяць спадає", "Waning gibbous"),
    "Последняя четверть": ("Остання чверть", "Last quarter"),
    "Убывающий серп": ("Старий місяць", "Waning crescent"),
    "🌄 Светает с {start:%H:%M} · ☀️ Полдень {mid:%H:%M} · 🌆 Темнеет к {end:%H:%M}": (
        "🌄 Світає з {start:%H:%M} · ☀️ Полудень {mid:%H:%M} · 🌆 Темніє до {end:%H:%M}",
        "🌄 First light {start:%H:%M} · ☀️ Solar noon {mid:%H:%M} · 🌆 Dark by {end:%H:%M}"),
    "🌅 Восход {rise:%H:%M} · 🌇 Заход {set:%H:%M}": ("🌅 Схід {rise:%H:%M} · 🌇 Захід {set:%H:%M}",
                                                    "🌅 Sunrise {rise:%H:%M} · 🌇 Sunset {set:%H:%M}"),
    " (день {h} ч {m:02d} мин)": (" (день {h} год {m:02d} хв)", " (daylight {h} h {m:02d} min)"),
    "🌙 Луна: восход {rise} · заход {set}": ("🌙 Місяць: схід {rise} · захід {set}",
                                            "🌙 Moon: rise {rise} · set {set}"),
    "{emoji} {name}, освещена на {lit}%": ("{emoji} {name}, освітлено {lit}%", "{emoji} {name}, {lit}% illuminated"),

    # ---------- Графики (charts.py) ----------
    "С": ("Пн", "N"),
    "СВ": ("ПнСх", "NE"),
    "В": ("Сх", "E"),
    "ЮВ": ("ПдСх", "SE"),
    "Ю": ("Пд", "S"),
    "ЮЗ": ("ПдЗх", "SW"),
    "З": ("Зх", "W"),
    "СЗ": ("ПнЗх", "NW"),
    "Вероятность осадков, %": ("Ймовірність опадів, %", "Chance of precipitation, %"),
    "Осадки, мм": ("Опади, мм", "Precipitation, mm"),
    "Температура, °C": ("Температура, °C", "Temperature, °C"),
    "{name}: ближайшие {n} ч": ("{name}: найближчі {n} год", "{name}: next {n} h"),
    "Днём (макс.)": ("Вдень (макс.)", "Day (max)"),
    "Ночью (мин.)": ("Вночі (мін.)", "Night (min)"),
    "{name}: прогноз на {n} дн.": ("{name}: прогноз на {n} дн.", "{name}: {n}-day forecast"),
    "{name}: ветер и влажность, {n} ч": ("{name}: вітер і вологість, {n} год", "{name}: wind and humidity, {n} h"),
    "{name}: ветер и влажность на {n} дн.": ("{name}: вітер і вологість на {n} дн.",
                                            "{name}: wind and humidity, {n} days"),
    "Порывы": ("Пориви", "Gusts"),
    "Ветер (макс.)": ("Вітер (макс.)", "Wind (max)"),
    "Ветер, м/с": ("Вітер, м/с", "Wind, m/s"),
    "Мин–макс": ("Мін–макс", "Min–max"),
    "Средняя": ("Середня", "Mean"),
    "Влажность, %": ("Вологість, %", "Humidity, %"),
    "Мои места: днём (линия) и ночью (пунктир)": ("Мої місця: вдень (лінія) і вночі (пунктир)",
                                                  "My places: day (solid) and night (dashed)"),
    "разброс": ("розкид", "spread"),
    "{name}: прогноз разных моделей": ("{name}: прогноз різних моделей", "{name}: forecasts of different models"),
    "Осадки за сутки": ("Опади за добу", "Daily precipitation"),
})

T.update({
    # ---------- Кнопки меню и общее (core.py) ----------
    "📍 Моя геолокация": ("📍 Моя геолокація", "📍 My location"),
    "🌤 Погода сейчас": ("🌤 Погода зараз", "🌤 Weather now"),
    "📅 Прогноз на неделю": ("📅 Прогноз на тиждень", "📅 Weekly forecast"),
    "❓ Помощь": ("❓ Допомога", "❓ Help"),
    "⭐ Мои места": ("⭐ Мої місця", "⭐ My places"),
    "📆 Выбрать дату": ("📆 Обрати дату", "📆 Pick a date"),
    "🔔 Рассылка": ("🔔 Розсилка", "🔔 Scheduled"),
    "📡 Связь": ("📡 Зв'язок", "📡 Status"),
    "⚠️ Предупреждения": ("⚠️ Попередження", "⚠️ Alerts"),
    "⚙️ Настройки": ("⚙️ Налаштування", "⚙️ Settings"),
    "Напишите название города или нажмите «📍 Моя геолокация»": (
        "Напишіть назву міста або натисніть «📍 Моя геолокація»",
        "Type a city name or tap “📍 My location”"),
    "Отправьте название города, координаты (например <code>51.18, 32.83</code>) "
    "или геолокацию — добавлю в «Мои места»": (
        "Надішліть назву міста, координати (наприклад <code>51.18, 32.83</code>) "
        "або геолокацію — додам у «Мої місця»",
        "Send a city name, coordinates (e.g. <code>51.18, 32.83</code>) "
        "or a location — I'll add it to “My places”"),
    "Начать и показать кнопки": ("Почати й показати кнопки", "Start and show the buttons"),
    "Погода сейчас: /weather Город": ("Погода зараз: /weather Місто", "Weather now: /weather City"),
    "Прогноз на неделю: /week Город": ("Прогноз на тиждень: /week Місто", "Weekly forecast: /week City"),
    "Погода на дату: /date 21.11 Город": ("Погода на дату: /date 21.11 Місто", "Weather for a date: /date 21.11 City"),
    "Мои места": ("Мої місця", "My places"),
    "Добавить место: /add Город или /add 51.18 32.83": ("Додати місце: /add Місто або /add 51.18 32.83",
                                                        "Add a place: /add City or /add 51.18 32.83"),
    "Удалить место: /del номер или название": ("Видалити місце: /del номер або назва",
                                               "Remove a place: /del number or name"),
    "Рассылка погоды: /subscribe Город 3ч": ("Розсилка погоди: /subscribe Місто 3год",
                                             "Scheduled weather: /subscribe City 3h"),
    "Мои рассылки": ("Мої розсилки", "My schedules"),
    "Отключить рассылку: /unsubscribe номер|all": ("Вимкнути розсилку: /unsubscribe номер|all",
                                                   "Turn off a schedule: /unsubscribe number|all"),
    "Предупреждения: заморозок, гроза, ветер": ("Попередження: заморозок, гроза, вітер",
                                                "Alerts: frost, thunderstorm, wind"),
    "Качество воздуха и пыльца: /air Город": ("Якість повітря й пилок: /air Місто",
                                              "Air quality and pollen: /air City"),
    "Погода на выходные: /weekend Город": ("Погода на вихідні: /weekend Місто", "Weekend weather: /weekend City"),
    "3 дня таблицей: /table Город": ("3 дні таблицею: /table Місто", "3 days as a table: /table City"),
    "Сравнить мои места": ("Порівняти мої місця", "Compare my places"),
    "Радар осадков: /radar Город": ("Радар опадів: /radar Місто", "Precipitation radar: /radar City"),
    "ECMWF, ICON и GFS на одном графике": ("ECMWF, ICON і GFS на одному графіку", "ECMWF, ICON and GFS on one chart"),
    "Итоги недели и точность прогноза": ("Підсумки тижня й точність прогнозу", "Week in review and forecast accuracy"),
    "Язык, источник погоды и качества воздуха": ("Мова, джерело погоди та якості повітря",
                                                 "Language, weather and air quality sources"),
    "Язык: русский, українська, English": ("Мова: русский, українська, English",
                                           "Language: русский, українська, English"),
    "Проверить связь с сервером": ("Перевірити зв'язок із сервером", "Check the connection to the server"),
    "Справка": ("Довідка", "Help"),
    "📅 Неделя": ("📅 Тиждень", "📅 Week"),
    "🌤 Сегодня": ("🌤 Сьогодні", "🌤 Today"),
    "🔄 Обновить": ("🔄 Оновити", "🔄 Refresh"),
    "⭐ В мои места": ("⭐ До моїх місць", "⭐ Save place"),
    "📆 Другая дата": ("📆 Інша дата", "📆 Another date"),
    "⏱ По часам": ("⏱ По годинах", "⏱ Hourly"),
    "🔔 Подписаться": ("🔔 Підписатися", "🔔 Subscribe"),
    "🌫 Воздух": ("🌫 Повітря", "🌫 Air"),
    "🏖 Выходные": ("🏖 Вихідні", "🏖 Weekend"),
    "📋 Таблица": ("📋 Таблиця", "📋 Table"),
    "🛰 Радар": ("🛰 Радар", "🛰 Radar"),
    "🧪 Модели": ("🧪 Моделі", "🧪 Models"),
    "📈 Итоги недели": ("📈 Підсумки тижня", "📈 Week in review"),
    "✖️ Отмена": ("✖️ Скасувати", "✖️ Cancel"),
    "<i>Модели для среднего сейчас не ответили — показан прогноз «Авто»</i>": (
        "<i>Моделі для середнього зараз не відповіли — показано прогноз «Авто»</i>",
        "<i>Models for the average didn't respond — showing the “Auto” forecast</i>"),
    "<i>Источник: OpenWeatherMap (дальше 5 дней — Open-Meteo)</i>": (
        "<i>Джерело: OpenWeatherMap (далі 5 днів — Open-Meteo)</i>",
        "<i>Source: OpenWeatherMap (beyond 5 days — Open-Meteo)</i>"),
    "<i>OpenWeatherMap сейчас не ответил — показан прогноз Open-Meteo</i>": (
        "<i>OpenWeatherMap зараз не відповів — показано прогноз Open-Meteo</i>",
        "<i>OpenWeatherMap didn't respond — showing the Open-Meteo forecast</i>"),
    "<i>Прогноз Open-Meteo: OpenWeatherMap не даёт прогноза на отдельные даты</i>": (
        "<i>Прогноз Open-Meteo: OpenWeatherMap не дає прогнозу на окремі дати</i>",
        "<i>Open-Meteo forecast: OpenWeatherMap has no forecasts for specific dates</i>"),
    "<i>Прогноз на дату — «Авто» Open-Meteo</i>": ("<i>Прогноз на дату — «Авто» Open-Meteo</i>",
                                                   "<i>Forecast for a date — Open-Meteo “Auto”</i>"),
    "<i>Модель прогноза: {m}</i>": ("<i>Модель прогнозу: {m}</i>", "<i>Forecast model: {m}</i>"),
    "📍 {name} — прогноз на сегодня": ("📍 {name} — прогноз на сьогодні", "📍 {name} — today's forecast"),
    "📍 {name} — прогноз на 7 дней": ("📍 {name} — прогноз на 7 днів", "📍 {name} — 7-day forecast"),
    "<i>обновлено в {t} по местному времени</i>": ("<i>оновлено о {t} за місцевим часом</i>",
                                                   "<i>updated at {t} local time</i>"),
    "Не удалось получить погоду, попробуйте чуть позже 🙏": ("Не вдалося отримати погоду, спробуйте трохи пізніше 🙏",
                                                             "Couldn't get the weather, please try again a bit later 🙏"),
    "Не удалось найти место, попробуйте чуть позже 🙏": ("Не вдалося знайти місце, спробуйте трохи пізніше 🙏",
                                                         "Couldn't search for the place, please try again later 🙏"),
    "Не нашёл «{q}» ни среди городов, ни на карте OpenStreetMap 🤷 Проверьте написание.": (
        "Не знайшов «{q}» ні серед міст, ні на мапі OpenStreetMap 🤷 Перевірте написання.",
        "Couldn't find “{q}” among cities or on the OpenStreetMap map 🤷 Check the spelling."),
    "🔎 Нашёл несколько мест «{q}». Какое нужно?": ("🔎 Знайшов кілька місць «{q}». Яке потрібне?",
                                                   "🔎 Found several places named “{q}”. Which one?"),
    "🌤 Сейчас": ("🌤 Зараз", "🌤 Now"),
    "Привет, {name}! 👋": ("Привіт, {name}! 👋", "Hi, {name}! 👋"),

    # ---------- Даты (dates.py, handlers/dates.py) ----------
    "Прогноз доступен максимум на 16 дней вперёд": ("Прогноз доступний щонайбільше на 16 днів уперед",
                                                    "Forecasts go up to 16 days ahead"),
    "Архив погоды начинается с 01.01.1940": ("Архів погоди починається з 01.01.1940",
                                            "The weather archive starts on 01.01.1940"),
    "Прошлые дни": ("Минулі дні", "Past days"),
    "Выберите дату": ("Оберіть дату", "Pick a date"),
    "◀ Прошлые дни": ("◀ Минулі дні", "◀ Past days"),
    "Ближайшие дни ▶": ("Найближчі дні ▶", "Next days ▶"),
    "✏️ Ввести дату": ("✏️ Ввести дату", "✏️ Type a date"),
    "Сегодня": ("Сьогодні", "Today"),
    "{name}: {day}, по часам": ("{name}: {day}, по годинах", "{name}: {day}, hourly"),
    "{name}: ветер и влажность, {day}": ("{name}: вітер і вологість, {day}", "{name}: wind and humidity, {day}"),
    "Не удалось получить погоду за эту дату, попробуйте чуть позже 🙏": (
        "Не вдалося отримати погоду за цю дату, спробуйте трохи пізніше 🙏",
        "Couldn't get the weather for this date, please try again later 🙏"),
    "Не понял дату. Примеры: <code>/date 21.11</code>, <code>/date 21.11.2026 Казань</code>, "
    "<code>/date завтра</code>, <code>/date вчера 51.18, 32.83</code>": (
        "Не зрозумів дату. Приклади: <code>/date 21.11</code>, <code>/date 21.11.2026 Львів</code>, "
        "<code>/date завтра</code>, <code>/date вчора 51.18, 32.83</code>",
        "I didn't get the date. Examples: <code>/date 21.11</code>, <code>/date 21.11.2026 London</code>, "
        "<code>/date tomorrow</code>, <code>/date yesterday 51.18, 32.83</code>"),
    "Напишите дату: <code>21.11</code>, <code>21.11.2026</code>, <code>завтра</code> или <code>вчера</code>": (
        "Напишіть дату: <code>21.11</code>, <code>21.11.2026</code>, <code>завтра</code> або <code>вчора</code>",
        "Type a date: <code>21.11</code>, <code>21.11.2026</code>, <code>tomorrow</code> or <code>yesterday</code>"),
    "Не понял дату, попробуйте так: <code>21.11</code> или <code>21.11.2026</code>": (
        "Не зрозумів дату, спробуйте так: <code>21.11</code> або <code>21.11.2026</code>",
        "I didn't get the date, try like this: <code>21.11</code> or <code>21.11.2026</code>"),
    "Кнопка устарела": ("Кнопка застаріла", "This button is outdated"),

    # ---------- Среднее моделей, нормы, места (ensemble.py, normals.py, places.py) ----------
    "Среднее {n} источников ({names})": ("Середнє {n} джерел ({names})", "Average of {n} sources ({names})"),
    ", сегодня почти не расходятся": (", сьогодні майже не розходяться", ", nearly agreeing today"),
    ", сегодня расходятся до {n}°": (", сьогодні розходяться до {n}°", ", differing by up to {n}° today"),
    "📈 Обычно {d:%d.%m}: днём {hi}°, ночью {lo}°": ("📈 Зазвичай {d:%d.%m}: вдень {hi}°, вночі {lo}°",
                                                    "📈 Normally on {d:%d.%m}: {hi}° by day, {lo}° at night"),
    ", осадки в {p}% лет": (", опади в {p}% років", ", precipitation in {p}% of years"),
    " — сегодня на {n}° теплее нормы": (" — сьогодні на {n}° тепліше за норму", " — today {n}° warmer than normal"),
    " — в этот день на {n}° теплее нормы": (" — цього дня на {n}° тепліше за норму",
                                           " — {n}° warmer than normal that day"),
    " — сегодня на {n}° холоднее нормы": (" — сьогодні на {n}° холодніше за норму",
                                         " — today {n}° colder than normal"),
    " — в этот день на {n}° холоднее нормы": (" — цього дня на {n}° холодніше за норму",
                                             " — {n}° colder than normal that day"),
    " — около нормы": (" — близько норми", " — about normal"),
    "Выбранное место": ("Вибране місце", "Selected place"),
    "Точка {lat:.2f}, {lon:.2f}": ("Точка {lat:.2f}, {lon:.2f}", "Point {lat:.2f}, {lon:.2f}"),
    "Ваше местоположение": ("Ваше місцезнаходження", "Your location"),

    # ---------- Поиск мест: типы объектов OpenStreetMap (geo.py) ----------
    "вершина": ("вершина", "peak"),
    "вулкан": ("вулкан", "volcano"),
    "горы": ("гори", "mountains"),
    "хребет": ("хребет", "ridge"),
    "перевал": ("перевал", "pass"),
    "станция": ("станція", "station"),
    "остановка": ("зупинка", "stop"),
    "аэропорт": ("аеропорт", "airport"),
    "озеро": ("озеро", "lake"),
    "водохранилище": ("водосховище", "reservoir"),
    "водоём": ("водойма", "water"),
    "река": ("річка", "river"),
    "залив": ("затока", "bay"),
    "пляж": ("пляж", "beach"),
    "остров": ("острів", "island"),
    "лес": ("ліс", "forest"),
    "парк": ("парк", "park"),
    "заповедник": ("заповідник", "nature reserve"),
    "нацпарк": ("нацпарк", "national park"),
    "достопримечательность": ("пам'ятка", "attraction"),
    "музей": ("музей", "museum"),
    "замок": ("замок", "castle"),
    "памятник": ("пам'ятник", "monument"),
    "смотровая площадка": ("оглядовий майданчик", "viewpoint"),
    "кемпинг": ("кемпінг", "campsite"),
    "приют": ("притулок", "mountain hut"),
    "горнолыжный курорт": ("гірськолижний курорт", "ski resort"),

    # ---------- Проверка связи (health.py, /ping) ----------
    "нет ответа": ("немає відповіді", "no response"),
    "{d} д {h} ч {m} мин": ("{d} д {h} год {m} хв", "{d} d {h} h {m} min"),
    "{h} ч {m} мин": ("{h} год {m} хв", "{h} h {m} min"),
    "{m} мин": ("{m} хв", "{m} min"),
    "{s} с": ("{s} с", "{s} s"),
    "🔴 {name}: ошибка — {detail}": ("🔴 {name}: помилка — {detail}", "🔴 {name}: error — {detail}"),
    " — медленно": (" — повільно", " — slow"),
    "🟢 {name}: {extra}{ms} мс{slow}": ("🟢 {name}: {extra}{ms} мс{slow}", "🟢 {name}: {extra}{ms} ms{slow}"),
    "📡 <b>Связь в порядке</b>": ("📡 <b>Зв'язок у порядку</b>", "📡 <b>All systems OK</b>"),
    "📡 <b>Есть проблемы со связью</b>": ("📡 <b>Є проблеми зі зв'язком</b>", "📡 <b>There are connection problems</b>"),
    "🟢 Сервер бота: работает, аптайм {up}": ("🟢 Сервер бота: працює, аптайм {up}", "🟢 Bot server: running, uptime {up}"),
    "     время {now:%H:%M:%S} UTC · {kyiv:%H:%M:%S} Киев ({now:%d.%m.%Y})": (
        "     час {now:%H:%M:%S} UTC · {kyiv:%H:%M:%S} Київ ({now:%d.%m.%Y})",
        "     time {now:%H:%M:%S} UTC · {kyiv:%H:%M:%S} Kyiv ({now:%d.%m.%Y})"),
    "🟢 Рассылки: работают, активных {n}": ("🟢 Розсилки: працюють, активних {n}", "🟢 Schedules: running, {n} active"),
    ", ближайшая {t:%d.%m %H:%M} (Киев)": (", найближча {t:%d.%m %H:%M} (Київ)", ", next at {t:%d.%m %H:%M} (Kyiv)"),
    "🔴 Рассылки: планировщик не отвечает (активных {n})": ("🔴 Розсилки: планувальник не відповідає (активних {n})",
                                                          "🔴 Schedules: the scheduler isn't responding ({n} active)"),
    "🏷 Версия бота: {v}": ("🏷 Версія бота: {v}", "🏷 Bot version: {v}"),
    "Open-Meteo прогноз": ("Open-Meteo прогноз", "Open-Meteo forecast"),
    "Open-Meteo поиск городов": ("Open-Meteo пошук міст", "Open-Meteo city search"),
    "Open-Meteo архив": ("Open-Meteo архів", "Open-Meteo archive"),
    "⏳ Проверяю…": ("⏳ Перевіряю…", "⏳ Checking…"),
    "🔴 Не удалось выполнить проверку, попробуйте позже": ("🔴 Не вдалося виконати перевірку, спробуйте пізніше",
                                                          "🔴 The check failed, please try later"),
    "Подождите {s:.0f} с перед следующей проверкой": ("Зачекайте {s:.0f} с перед наступною перевіркою",
                                                      "Please wait {s:.0f} s before the next check"),
    "Подождите {s:.0f} с": ("Зачекайте {s:.0f} с", "Please wait {s:.0f} s"),
    "🔄 Проверить снова": ("🔄 Перевірити знову", "🔄 Check again"),
    "Сообщение устарело, отправьте /ping": ("Повідомлення застаріло, надішліть /ping", "This message is outdated, send /ping"),
})

T.update({
    # ---------- Настройки (prefs.py, handlers/settings.py) ----------
    "⚙️ <b>Настройки</b>": ("⚙️ <b>Налаштування</b>", "⚙️ <b>Settings</b>"),
    "ЯЗЫК": ("МОВА", "LANGUAGE"),
    "<b>ПОГОДА</b> — источник прогноза:": ("<b>ПОГОДА</b> — джерело прогнозу:", "<b>WEATHER</b> — forecast source:"),
    "<b>КАЧЕСТВО ВОЗДУХА</b>:": ("<b>ЯКІСТЬ ПОВІТРЯ</b>:", "<b>AIR QUALITY</b>:"),
    "<b>КРАТКАЯ СВОДКА</b> (рассылки «кратко»): ": ("<b>КОРОТКЕ ЗВЕДЕННЯ</b> (розсилки «коротко»): ",
                                                   "<b>SHORT SUMMARY</b> (“short” schedules): "),
    "<b>ИТОГИ НЕДЕЛИ</b> — погода за неделю и точность прогноза:": (
        "<b>ПІДСУМКИ ТИЖНЯ</b> — погода за тиждень і точність прогнозу:",
        "<b>WEEK IN REVIEW</b> — the past week's weather and forecast accuracy:"),
    "Авто": ("Авто", "Auto"),
    "Open-Meteo сам выбирает самую точную модель для места.": (
        "Open-Meteo сам обирає найточнішу модель для місця.",
        "Open-Meteo picks the most accurate model for the place."),
    "Европейский центр прогнозов — одна из самых точных моделей в мире.": (
        "Європейський центр прогнозів — одна з найточніших моделей у світі.",
        "European Centre for Medium-Range Weather Forecasts — one of the most accurate models in the world."),
    "Немецкая служба погоды, подробная сетка для Европы.": ("Німецька служба погоди, детальна сітка для Європи.",
                                                            "German Weather Service, a detailed grid for Europe."),
    "Американская глобальная модель.": ("Американська глобальна модель.", "American global model."),
    "Среднее": ("Середнє", "Average"),
    "Среднее ECMWF, ICON, GFS (и OpenWeatherMap, если он подключён): "
    "ошибки отдельных моделей сглаживаются. Погода словами, восход и УФ — от «Авто».": (
        "Середнє ECMWF, ICON, GFS (і OpenWeatherMap, якщо він підключений): "
        "помилки окремих моделей згладжуються. Погода словами, схід і УФ — від «Авто».",
        "Average of ECMWF, ICON, GFS (and OpenWeatherMap, if connected): "
        "errors of single models even out. Weather in words, sunrise and UV come from “Auto”."),
    " (и OpenWeatherMap, если он подключён)": (" (і OpenWeatherMap, якщо він підключений)",
                                              " (and OpenWeatherMap, if connected)"),
    "Независимый сервис со своим пересчётом моделей и наблюдений. Прогноз на 5 дней, "
    "дальше, а также восход и УФ — из Open-Meteo.": (
        "Незалежний сервіс із власним перерахунком моделей і спостережень. Прогноз на 5 днів, "
        "далі, а також схід і УФ — з Open-Meteo.",
        "An independent service with its own blend of models and observations. 5-day forecast; "
        "later days, sunrise and UV come from Open-Meteo."),
    "Модель Copernicus для любой точки: индекс EAQI и пыльца.": ("Модель Copernicus для будь-якої точки: індекс EAQI і пилок.",
                                                                "Copernicus model for any point: EAQI index and pollen."),
    "Измерения ближайшей станции в пределах 5 км. Где станции рядом нет — не будет и значения.": (
        "Вимірювання найближчої станції в межах 5 км. Де станції поруч немає — не буде й значення.",
        "Readings from the nearest station within 5 km. No station nearby — no value."),
    "Выключено": ("Вимкнено", "Off"),
    "Кнопки и команды качества воздуха не будет.": ("Кнопок і команд якості повітря не буде.",
                                                    "No air quality buttons or commands."),
    "По воскресеньям": ("Щонеділі", "On Sundays"),
    "Вечером в воскресенье — итоги недели для ⭐ Моих мест (до трёх).": (
        "У неділю ввечері — підсумки тижня для ⭐ Моїх місць (до трьох).",
        "Sunday evening — week in review for ⭐ My places (up to three)."),
    "Не присылать": ("Не надсилати", "Don't send"),
    "Итоги можно посмотреть в любой момент: /review.": ("Підсумки можна переглянути будь-коли: /review.",
                                                        "You can check the review any time: /review."),
    "⚠️ Для OpenWeatherMap на сервере не задан ключ — до этого показываю Open-Meteo.": (
        "⚠️ Для OpenWeatherMap на сервері не задано ключ — доти показую Open-Meteo.",
        "⚠️ No OpenWeatherMap key on the server — showing Open-Meteo until then."),
    "⚠️ Для WAQI на сервере пока не задан токен — до этого показываю Open-Meteo.": (
        "⚠️ Для WAQI на сервері ще не задано токен — доти показую Open-Meteo.",
        "⚠️ No WAQI token on the server yet — showing Open-Meteo until then."),
    "Нажмите, чтобы выбрать. Настройка действует на прогнозы, рассылки и предупреждения.": (
        "Натисніть, щоб обрати. Налаштування діє на прогнози, розсилки й попередження.",
        "Tap to choose. Settings apply to forecasts, schedules and alerts."),
    "Хотя бы одно поле должно остаться": ("Хоча б одне поле має залишитися", "At least one field must stay on"),
    "{field}: показывать": ("{field}: показувати", "{field}: shown"),
    "{field}: не показывать": ("{field}: не показувати", "{field}: hidden"),
    "Выбрано: {v}": ("Обрано: {v}", "Selected: {v}"),
    "✅ Язык: {name}. Кнопки внизу — тоже на нём.": ("✅ Мова: {name}. Кнопки внизу — теж нею.",
                                                    "✅ Language: {name}. The buttons below have switched too."),

    # ---------- Предупреждения (handlers/settings.py) ----------
    "⚠️ Предупреждения для «{name}»: включено {on} из {total}.\n"
    "Нажмите, чтобы включить или выключить. Ночью (23–7 по местному времени) бот молчит.": (
        "⚠️ Попередження для «{name}»: увімкнено {on} з {total}.\n"
        "Натисніть, щоб увімкнути чи вимкнути. Вночі (23–7 за місцевим часом) бот мовчить.",
        "⚠️ Alerts for “{name}”: {on} of {total} on.\n"
        "Tap to turn on or off. At night (23–7 local time) the bot stays quiet."),
    "🗑 Отключить для места": ("🗑 Вимкнути для місця", "🗑 Turn off for this place"),
    "↩️ Все места": ("↩️ Усі місця", "↩️ All places"),
    "➕ Для последнего места": ("➕ Для останнього місця", "➕ For the last place"),
    "⚠️ Предупреждений пока нет. Бот может сам написать, если будет заморозок, гроза, сильный ветер, "
    "жара, мороз, резкий перепад температуры или скоро пойдёт дождь.\n"
    "Включите их кнопкой ниже или «⚠️ Предупреждения» под прогнозом.": (
        "⚠️ Попереджень поки немає. Бот може сам написати, якщо буде заморозок, гроза, сильний вітер, "
        "спека, мороз, різкий перепад температури або скоро піде дощ.\n"
        "Увімкніть їх кнопкою нижче або «⚠️ Попередження» під прогнозом.",
        "⚠️ No alerts yet. The bot can message you about frost, thunderstorms, strong wind, "
        "heat, severe cold, a sharp temperature swing or rain coming soon.\n"
        "Turn them on with the button below or “⚠️ Alerts” under a forecast."),
    "⚠️ Места с предупреждениями (нажмите, чтобы настроить):": ("⚠️ Місця з попередженнями (натисніть, щоб налаштувати):",
                                                                "⚠️ Places with alerts (tap to set up):"),
    "Предупреждения уже включены для {n} мест — отключите лишнее в /alerts": (
        "Попередження вже увімкнено для {n} місць — вимкніть зайве в /alerts",
        "Alerts are already on for {n} places — turn some off in /alerts"),
    "Сообщение устарело, откройте /alerts": ("Повідомлення застаріло, відкрийте /alerts",
                                             "This message is outdated, open /alerts"),
    "Отключено: {name}": ("Вимкнено: {name}", "Turned off: {name}"),
    "Уже отключено": ("Уже вимкнено", "Already off"),
    "🌤 Погода": ("🌤 Погода", "🌤 Weather"),
    "⚙️ Настроить": ("⚙️ Налаштувати", "⚙️ Set up"),

    # ---------- Мои места (handlers/places.py) ----------
    "↩️ Готово": ("↩️ Готово", "↩️ Done"),
    "Нажмите место, которое нужно удалить:": ("Натисніть місце, яке треба видалити:", "Tap the place to remove:"),
    "➕ Добавить": ("➕ Додати", "➕ Add"),
    "🗑 Удалить": ("🗑 Видалити", "🗑 Remove"),
    "📊 Сравнить": ("📊 Порівняти", "📊 Compare"),
    "⭐ Мои места:": ("⭐ Мої місця:", "⭐ My places:"),
    "⭐ Список мест пуст. Нажмите «➕ Добавить» или используйте /add <i>город</i>": (
        "⭐ Список місць порожній. Натисніть «➕ Додати» або скористайтеся /add <i>місто</i>",
        "⭐ No places yet. Tap “➕ Add” or use /add <i>city</i>"),
    "✅ Добавлено: {place}": ("✅ Додано: {place}", "✅ Added: {place}"),
    "✅ Обновлено: {place}": ("✅ Оновлено: {place}", "✅ Updated: {place}"),
    "Уже есть в ваших местах: {place}": ("Уже є у ваших місцях: {place}", "Already in your places: {place}"),
    "В списке уже {n} мест — удалите лишнее через /places": ("У списку вже {n} місць — видаліть зайве через /places",
                                                             "You already have {n} places — remove some via /places"),
    "Не понял координаты. Пример: <code>/add 51.18 32.83 Дача</code> "
    "(широта от -90 до 90, долгота от -180 до 180)": (
        "Не зрозумів координати. Приклад: <code>/add 51.18 32.83 Дача</code> "
        "(широта від -90 до 90, довгота від -180 до 180)",
        "I didn't get the coordinates. Example: <code>/add 51.18 32.83 Cottage</code> "
        "(latitude -90 to 90, longitude -180 to 180)"),
    "Список мест пуст.": ("Список місць порожній.", "You have no places."),
    "🗑 Удалено: {place}": ("🗑 Видалено: {place}", "🗑 Removed: {place}"),
    "Не нашёл «{key}» в ваших местах. Номера — в /places": ("Не знайшов «{key}» у ваших місцях. Номери — у /places",
                                                          "Couldn't find “{key}” in your places. Numbers are in /places"),
    "Сообщение устарело, откройте /places": ("Повідомлення застаріло, відкрийте /places",
                                             "This message is outdated, open /places"),
    "Уже удалено": ("Уже видалено", "Already removed"),
    "🗑 Да, удалить": ("🗑 Так, видалити", "🗑 Yes, remove"),
    "↩️ Нет": ("↩️ Ні", "↩️ No"),
    "Удалить «{name}» из ваших мест?": ("Видалити «{name}» з ваших місць?", "Remove “{name}” from your places?"),
    "Удалено: {name}": ("Видалено: {name}", "Removed: {name}"),
    "⭐ Добавлено: {name}": ("⭐ Додано: {name}", "⭐ Added: {name}"),
    "⭐ Обновлено": ("⭐ Оновлено", "⭐ Updated"),
    "Уже есть в ваших местах": ("Уже є у ваших місцях", "Already in your places"),
    "В списке уже {n} мест": ("У списку вже {n} місць", "You already have {n} places"),
    "Для сравнения нужно хотя бы два места в «⭐ Мои места» — добавьте их через /add": (
        "Для порівняння потрібно хоча б два місця в «⭐ Мої місця» — додайте їх через /add",
        "To compare, you need at least two places in “⭐ My places” — add them with /add"),
})

T.update({
    # ---------- Рассылки (subs.py, handlers/subs.py) ----------
    "ежедневно": ("щодня", "daily"),
    "по будням": ("по буднях", "on weekdays"),
    "по выходным": ("по вихідних", "on weekends"),
    "по {days}": ("по {days}", "on {days}"),
    "{days} в {times}": ("{days} о {times}", "{days} at {times}"),
    "каждый час": ("щогодини", "every hour"),
    "раз в сутки": ("раз на добу", "once a day"),
    "каждые {h} ч": ("кожні {h} год", "every {h} h"),
    "если ниже {t}°": ("якщо нижче {t}°", "if below {t}°"),
    "если выше {t}°": ("якщо вище {t}°", "if above {t}°"),
    "если будут осадки": ("якщо будуть опади", "if precipitation is expected"),
    "если будет снег": ("якщо буде сніг", "if snow is expected"),
    "если будет мороз": ("якщо буде мороз", "if frost is expected"),
    "Каждый час": ("Щогодини", "Every hour"),
    "Каждые {h} ч": ("Кожні {h} год", "Every {h} h"),
    "✏️ Своё время": ("✏️ Свій час", "✏️ Custom time"),
    "кратко": ("коротко", "short"),
    "полно": ("повністю", "full"),
    "🖼 Присылать полностью": ("🖼 Надсилати повністю", "🖼 Send in full"),
    "📄 Присылать кратко": ("📄 Надсилати коротко", "📄 Send short"),
    "🔔 Мои рассылки": ("🔔 Мої розсилки", "🔔 My schedules"),
    "🖼 Полно": ("🖼 Повністю", "🖼 Full"),
    "📄 Кратко": ("📄 Коротко", "📄 Short"),
    "➕ Новая рассылка": ("➕ Нова розсилка", "➕ New schedule"),
    "🔔 Рассылок пока нет. Бот может сам присылать погоду каждый час, раз в сутки или в выбранное время.": (
        "🔔 Розсилок поки немає. Бот може сам надсилати погоду щогодини, раз на добу або в обраний час.",
        "🔔 No schedules yet. The bot can send you the weather every hour, once a day or at chosen times."),
    "{i}. {name} — {what}, следующая {next}": ("{i}. {name} — {what}, наступна {next}", "{i}. {name} — {what}, next {next}"),
    "🔔 Ваши рассылки (❌ — отключить, 📄/🖼 — краткий или полный формат):": (
        "🔔 Ваші розсилки (❌ — вимкнути, 📄/🖼 — короткий або повний формат):",
        "🔔 Your schedules (❌ — turn off, 📄/🖼 — short or full format):"),
    "🔔 Как часто присылать погоду для «{name}»?\nВремя для ежедневной рассылки — по местному времени этого места.": (
        "🔔 Як часто надсилати погоду для «{name}»?\nЧас щоденної розсилки — за місцевим часом цього місця.",
        "🔔 How often should I send the weather for “{name}”?\nDaily times are in that place's local time."),
    "Не удалось узнать часовой пояс места, попробуйте чуть позже 🙏": (
        "Не вдалося дізнатися часовий пояс місця, спробуйте трохи пізніше 🙏",
        "Couldn't get the place's time zone, please try again later 🙏"),
    "У вас уже {n} рассылок — отключите лишнюю в /subs": ("У вас уже {n} розсилок — вимкніть зайву в /subs",
                                                        "You already have {n} schedules — turn one off in /subs"),
    "✅ Рассылка включена: {name} — {what}.\nСледующая: {next} ({tz}).\nУправление — /subs": (
        "✅ Розсилку увімкнено: {name} — {what}.\nНаступна: {next} ({tz}).\nКерування — /subs",
        "✅ Schedule on: {name} — {what}.\nNext: {next} ({tz}).\nManage — /subs"),
    "Не понял условие. Примеры: <code>если дождь</code>, <code>если снег</code>, "
    "<code>если мороз</code>, <code>если ниже -5</code>, <code>если выше 25</code>": (
        "Не зрозумів умову. Приклади: <code>якщо дощ</code>, <code>якщо сніг</code>, "
        "<code>якщо мороз</code>, <code>якщо нижче -5</code>, <code>якщо вище 25</code>",
        "I didn't get the condition. Examples: <code>if rain</code>, <code>if snow</code>, "
        "<code>if frost</code>, <code>if below -5</code>, <code>if above 25</code>"),
    "Для рассылки с условием укажите и время, например: <code>/subscribe Бахмач 07:00 если дождь</code>": (
        "Для розсилки з умовою вкажіть і час, наприклад: <code>/subscribe Бахмач 07:00 якщо дощ</code>",
        "For a conditional schedule, give a time too, e.g. <code>/subscribe Kyiv 07:00 if rain</code>"),
    "🔕 Отключено рассылок: {n}": ("🔕 Вимкнено розсилок: {n}", "🔕 Schedules turned off: {n}"),
    "Рассылок не было.": ("Розсилок не було.", "There were no schedules."),
    "🔕 Отключена: {name} — {what}": ("🔕 Вимкнено: {name} — {what}", "🔕 Turned off: {name} — {what}"),
    "Нет рассылки с таким номером. Список — /subs": ("Немає розсилки з таким номером. Список — /subs",
                                                     "No schedule with that number. List — /subs"),
    "Сообщение устарело, используйте /subscribe": ("Повідомлення застаріло, скористайтеся /subscribe",
                                                   "This message is outdated, use /subscribe"),
    "Напишите время (до {n}), например <code>07:30</code> или <code>08:00, 20:00</code>": (
        "Напишіть час (до {n}), наприклад <code>07:30</code> або <code>08:00, 20:00</code>",
        "Type the time (up to {n}), e.g. <code>07:30</code> or <code>08:00, 20:00</code>"),
    "Не понял расписание, попробуйте /subscribe ещё раз": ("Не зрозумів розклад, спробуйте /subscribe ще раз",
                                                          "I didn't get the schedule, try /subscribe again"),
    "Сообщение устарело, откройте /subs": ("Повідомлення застаріло, відкрийте /subs", "This message is outdated, open /subs"),
    "🔔 Для какого места рассылка? Другой город — <code>/subscribe Город</code>": (
        "🔔 Для якого місця розсилка? Інше місто — <code>/subscribe Місто</code>",
        "🔔 Which place is the schedule for? Another city — <code>/subscribe City</code>"),
    "Рассылка уже отключена": ("Розсилку вже вимкнено", "The schedule is already off"),
    "Теперь кратко: три строки без графиков": ("Тепер коротко: три рядки без графіків",
                                               "Now short: three lines without charts"),
    "Теперь полностью, с графиками": ("Тепер повністю, з графіками", "Now in full, with charts"),
    "🔕 Рассылка отключена": ("🔕 Розсилку вимкнено", "🔕 Schedule turned off"),
    "Уже отключена": ("Уже вимкнено", "Already off"),
    "Не понял время. Пример: <code>07:30</code> или <code>08:00, 20:00</code> (не больше {n})": (
        "Не зрозумів час. Приклад: <code>07:30</code> або <code>08:00, 20:00</code> (не більше {n})",
        "I didn't get the time. Example: <code>07:30</code> or <code>08:00, 20:00</code> (up to {n})"),
    "📊 Подробно": ("📊 Детально", "📊 Details"),
    "🔔 <b>Рассылка:</b> {what}": ("🔔 <b>Розсилка:</b> {what}", "🔔 <b>Scheduled:</b> {what}"),

    # ---------- Погода, воздух, выходные, таблица (handlers/weather.py) ----------
    "Этот список устарел — напишите название ещё раз": ("Цей список застарів — напишіть назву ще раз",
                                                        "This list is outdated — type the name again"),
    "Отменено": ("Скасовано", "Cancelled"),
    "Отменено.": ("Скасовано.", "Cancelled."),
    "🌫 Качество воздуха выключено. Включить — /settings": ("🌫 Якість повітря вимкнено. Увімкнути — /settings",
                                                           "🌫 Air quality is off. Turn it on — /settings"),
    "⚠️ WAQI сейчас не отвечает — показываю данные Open-Meteo.": ("⚠️ WAQI зараз не відповідає — показую дані Open-Meteo.",
                                                                 "⚠️ WAQI isn't responding — showing Open-Meteo data."),
    "⚠️ Для WAQI на сервере не задан токен (WAQI_TOKEN) — показываю данные Open-Meteo.": (
        "⚠️ Для WAQI на сервері не задано токен (WAQI_TOKEN) — показую дані Open-Meteo.",
        "⚠️ No WAQI token (WAQI_TOKEN) on the server — showing Open-Meteo data."),
    "Не удалось получить данные о воздухе, попробуйте чуть позже 🙏": (
        "Не вдалося отримати дані про повітря, спробуйте трохи пізніше 🙏",
        "Couldn't get air quality data, please try again later 🙏"),
    "Не удалось получить прогноз, попробуйте чуть позже 🙏": ("Не вдалося отримати прогноз, спробуйте трохи пізніше 🙏",
                                                             "Couldn't get the forecast, please try again later 🙏"),
    "Кнопка устарела, запросите прогноз заново": ("Кнопка застаріла, запитайте прогноз знову",
                                                  "This button is outdated, request the forecast again"),
    "Сообщение устарело, запросите прогноз заново": ("Повідомлення застаріло, запитайте прогноз знову",
                                                     "This message is outdated, request the forecast again"),
    "Уже актуально": ("Уже актуально", "Already up to date"),
    "🔄 Обновлено": ("🔄 Оновлено", "🔄 Refreshed"),
    "🏖 <b>Выходные — {name}</b>": ("🏖 <b>Вихідні — {name}</b>", "🏖 <b>Weekend — {name}</b>"),
    "🌙 Сегодня уже вечер — показываю завтра.": ("🌙 Сьогодні вже вечір — показую завтра.",
                                                "🌙 It's already evening — showing tomorrow."),
    "🌙 Сегодня уже вечер — показываю следующие выходные.": ("🌙 Сьогодні вже вечір — показую наступні вихідні.",
                                                            "🌙 It's already evening — showing next weekend."),
    "Нет прогноза на выходные 🤷": ("Немає прогнозу на вихідні 🤷", "No weekend forecast 🤷"),
    "сегодня": ("сьогодні", "today"),
    "☔️ Вероятность осадков {p}%": ("☔️ Ймовірність опадів {p}%", "☔️ Chance of precipitation {p}%"),
    ", {mm:.1f} мм": (", {mm:.1f} мм", ", {mm:.1f} mm"),
    "💨 Ветер до {w} м/с": ("💨 Вітер до {w} м/с", "💨 Wind up to {w} m/s"),
    "⛈ Возможна гроза — планы лучше под крышей": ("⛈ Можлива гроза — плани краще під дахом",
                                                  "⛈ Thunderstorms possible — better plan something indoors"),
    "🌨 Снежно — тёплая обувь и запас времени на дорогу": ("🌨 Сніжно — тепле взуття й запас часу на дорогу",
                                                         "🌨 Snowy — warm shoes and extra time for the road"),
    "☔️ Скорее дождливо — зонт обязателен": ("☔️ Радше дощово — парасолька обов'язкова",
                                            "☔️ Likely rainy — take an umbrella"),
    "💨 Ветрено — для прогулок не лучший день": ("💨 Вітряно — для прогулянок не найкращий день",
                                                "💨 Windy — not the best day for a walk"),
    "😎 Отличный день для прогулки или поездки": ("😎 Чудовий день для прогулянки чи поїздки",
                                                "😎 A great day for a walk or a trip"),
    "🌨 Возможен небольшой снег — одевайтесь теплее": ("🌨 Можливий невеликий сніг — вдягайтеся тепліше",
                                                       "🌨 Some light snow possible — dress warmly"),
    "👍 Сухо — можно гулять, одевайтесь по погоде": ("👍 Сухо — можна гуляти, вдягайтеся за погодою",
                                                   "👍 Dry — good for a walk, dress for the weather"),
    "🤔 Переменчиво — возьмите зонт на всякий случай": ("🤔 Мінливо — візьміть парасольку про всяк випадок",
                                                      "🤔 Changeable — take an umbrella just in case"),
    "👉 Для дел на улице лучше суббота": ("👉 Для справ на вулиці краще субота", "👉 Saturday is better for outdoor plans"),
    "👉 Для дел на улице лучше воскресенье": ("👉 Для справ на вулиці краще неділя",
                                             "👉 Sunday is better for outdoor plans"),
    "📊 <b>Сравнение моих мест</b>": ("📊 <b>Порівняння моїх місць</b>", "📊 <b>My places compared</b>"),
    "📍 <b>{name}</b>: нет данных 🙏": ("📍 <b>{name}</b>: немає даних 🙏", "📍 <b>{name}</b>: no data 🙏"),
    " (ощущ. {t}°)": (" (відч. {t}°)", " (feels {t}°)"),
    "сегодня {lo}…{hi}°, ☔️ {p}%": ("сьогодні {lo}…{hi}°, ☔️ {p}%", "today {lo}…{hi}°, ☔️ {p}%"),
    "🔥 Теплее всего сейчас: {name} ({t}°)": ("🔥 Найтепліше зараз: {name} ({t}°)", "🔥 Warmest now: {name} ({t}°)"),
    "❄️ Холоднее всего: {name} ({t}°)": ("❄️ Найхолодніше: {name} ({t}°)", "❄️ Coldest: {name} ({t}°)"),
    "📋 <b>{name}</b> — на {n} дня по периодам": ("📋 <b>{name}</b> — на {n} дні за періодами",
                                                 "📋 <b>{name}</b> — {n} days by time of day"),
    "утро": ("ранок", "morn"),
    "день": ("день", "day"),
    "вечер": ("вечір", "eve"),
    "ночь": ("ніч", "night"),
    "дождь": ("дощ", "rain"),
    "ветер": ("вітер", "wind"),
    "м/с": ("м/с", "m/s"),
})

T.update({
    # ---------- Радар (radar.py, handlers/extras.py) ----------
    "Прогноз осадков на ближайшие часы сейчас недоступен 🙏": ("Прогноз опадів на найближчі години зараз недоступний 🙏",
                                                              "The precipitation nowcast is unavailable right now 🙏"),
    "🛰 <b>{name}</b> — радар осадков, снимок {t:%H:%M}": ("🛰 <b>{name}</b> — радар опадів, знімок {t:%H:%M}",
                                                         "🛰 <b>{name}</b> — precipitation radar, image at {t:%H:%M}"),
    "Красная точка — место, круг — {km} км. Синие и жёлтые пятна — осадки "
    "(чем ярче, тем сильнее). Новый снимок каждые 10 минут.": (
        "Червона точка — місце, коло — {km} км. Сині й жовті плями — опади "
        "(що яскравіші, то сильніші). Новий знімок кожні 10 хвилин.",
        "The red dot is the place, the circle is {km} km. Blue and yellow patches are precipitation "
        "(brighter means heavier). A new image every 10 minutes."),
    "Снимок радара сейчас недоступен, попробуйте чуть позже 🙏": ("Знімок радара зараз недоступний, спробуйте трохи пізніше 🙏",
                                                                 "The radar image is unavailable, please try again later 🙏"),
    "🔄 Обновить радар": ("🔄 Оновити радар", "🔄 Refresh radar"),
    "🔄 Ещё раз": ("🔄 Ще раз", "🔄 Try again"),
    "Прогноза осадков по 15 минут для этого места нет 🤷": ("Прогнозу опадів по 15 хвилин для цього місця немає 🤷",
                                                           "No 15-minute precipitation forecast for this place 🤷"),
    "☀️ В ближайшие {n} ч осадков не ожидается": ("☀️ Найближчі {n} год опадів не очікується",
                                                 "☀️ No precipitation expected in the next {n} h"),
    "Сейчас идёт снег": ("Зараз іде сніг", "It's snowing now"),
    "Сейчас идёт дождь": ("Зараз іде дощ", "It's raining now"),
    ", закончится около {t:%H:%M}": (", закінчиться близько {t:%H:%M}", ", should stop around {t:%H:%M}"),
    " и не закончится в ближайшие {n} ч": (" і не закінчиться найближчі {n} год", " and won't stop in the next {n} h"),
    "Снег начнётся около {t:%H:%M}": ("Сніг почнеться близько {t:%H:%M}", "Snow will start around {t:%H:%M}"),
    "Дождь начнётся около {t:%H:%M}": ("Дощ почнеться близько {t:%H:%M}", "Rain will start around {t:%H:%M}"),
    ", продлится до ~{t:%H:%M}": (", триватиме до ~{t:%H:%M}", ", lasting until ~{t:%H:%M}"),
    ", до {mm:.1f} мм за 15 минут": (", до {mm:.1f} мм за 15 хвилин", ", up to {mm:.1f} mm per 15 minutes"),

    # ---------- Сравнение моделей (spread.py) ----------
    "Не удалось получить прогноз моделей, попробуйте чуть позже 🙏": (
        "Не вдалося отримати прогноз моделей, спробуйте трохи пізніше 🙏",
        "Couldn't get the model forecasts, please try again later 🙏"),
    "🧪 <b>{name}</b> — что говорят разные модели": ("🧪 <b>{name}</b> — що кажуть різні моделі",
                                                    "🧪 <b>{name}</b> — what different models say"),
    ", 💧 {mm:.1f} мм": (", 💧 {mm:.1f} мм", ", 💧 {mm:.1f} mm"),
    ", 💧 {a:.1f}–{b:.1f} мм": (", 💧 {a:.1f}–{b:.1f} мм", ", 💧 {a:.1f}–{b:.1f} mm"),
    " (не все модели)": (" (не всі моделі)", " (not all models)"),
    "{mark} {wd} {d:%d.%m}: днём {hi}°, ночью {lo}°{rain}{note}": (
        "{mark} {wd} {d:%d.%m}: вдень {hi}°, вночі {lo}°{rain}{note}",
        "{mark} {wd} {d:%d.%m}: day {hi}°, night {lo}°{rain}{note}"),
    "Модели не прислали данных 🤷": ("Моделі не надіслали даних 🤷", "The models sent no data 🤷"),
    "Модели согласны на всю неделю — прогнозу можно доверять 👍": (
        "Моделі згодні на весь тиждень — прогнозу можна довіряти 👍",
        "The models agree for the whole week — the forecast is reliable 👍"),
    "Модели расходятся уже сегодня — погода может сильно отличаться от прогноза.": (
        "Моделі розходяться вже сьогодні — погода може сильно відрізнятися від прогнозу.",
        "The models disagree already today — the weather may differ a lot from the forecast."),
    "Модели согласны до {wd} {d:%d.%m}, дальше прогноз менее надёжен.": (
        "Моделі згодні до {wd} {d:%d.%m}, далі прогноз менш надійний.",
        "The models agree until {wd} {d:%d.%m}; after that the forecast is less reliable."),
    "✅ разница до 2° · 🟡 до 4° или спорный дождь · ⚠️ больше 4°": (
        "✅ різниця до 2° · 🟡 до 4° або спірний дощ · ⚠️ більше 4°",
        "✅ difference up to 2° · 🟡 up to 4° or disputed rain · ⚠️ more than 4°"),
    "Модели: ": ("Моделі: ", "Models: "),

    # ---------- Итоги недели (review.py) ----------
    "Не удалось получить погоду за неделю, попробуйте чуть позже 🙏": (
        "Не вдалося отримати погоду за тиждень, спробуйте трохи пізніше 🙏",
        "Couldn't get the past week's weather, please try again later 🙏"),
    "Нет данных о прошедшей неделе 🤷": ("Немає даних про минулий тиждень 🤷", "No data for the past week 🤷"),
    "📈 <b>{name}</b> — итоги недели {a:%d.%m}–{b:%d.%m}": ("📈 <b>{name}</b> — підсумки тижня {a:%d.%m}–{b:%d.%m}",
                                                          "📈 <b>{name}</b> — week in review {a:%d.%m}–{b:%d.%m}"),
    ", с осадками": (", з опадами", ", with precipitation"),
    "  {mark} прогноз {lo}…{hi}°{rain}": ("  {mark} прогноз {lo}…{hi}°{rain}", "  {mark} forecast {lo}…{hi}°{rain}"),
    "🌡 Средняя температура {mean:+.1f}°. Теплее всего — {wd1} ({t1}°), холоднее всего — {wd2} ({t2}°)": (
        "🌡 Середня температура {mean:+.1f}°. Найтепліше — {wd1} ({t1}°), найхолодніше — {wd2} ({t2}°)",
        "🌡 Mean temperature {mean:+.1f}°. Warmest — {wd1} ({t1}°), coldest — {wd2} ({t2}°)"),
    "💧 Осадки: {mm:.1f} мм, {n} дн. из {total}": ("💧 Опади: {mm:.1f} мм, {n} дн. з {total}",
                                                 "💧 Precipitation: {mm:.1f} mm on {n} of {total} days"),
    "💧 Неделя без осадков": ("💧 Тиждень без опадів", "💧 A week without precipitation"),
    "🎯 Прогноз на завтра ({n} дн.): ошибка днём в среднем {hi:.1f}°, ночью {lo:.1f}°; "
    "осадки угаданы в {hits} из {n}": (
        "🎯 Прогноз на завтра ({n} дн.): похибка вдень у середньому {hi:.1f}°, вночі {lo:.1f}°; "
        "опади вгадано в {hits} з {n}",
        "🎯 Next-day forecast ({n} days): mean error {hi:.1f}° by day, {lo:.1f}° at night; "
        "precipitation right on {hits} of {n}"),
    "✅ ошибка до 2° и осадки угаданы · 🟡 до 4° · ❌ больше 4°": (
        "✅ похибка до 2° і опади вгадано · 🟡 до 4° · ❌ більше 4°",
        "✅ error up to 2° and precipitation right · 🟡 up to 4° · ❌ more than 4°"),
    "🎯 Точность прогноза: бот записывает прогнозы с {d:%d.%m}, для этого места записей пока нет. "
    "Записываются места из ⭐ Моих мест, рассылок и предупреждений.": (
        "🎯 Точність прогнозу: бот записує прогнози з {d:%d.%m}, для цього місця записів поки немає. "
        "Записуються місця з ⭐ Моїх місць, розсилок і попереджень.",
        "🎯 Forecast accuracy: the bot has been logging forecasts since {d:%d.%m}, none for this place yet. "
        "It logs places from ⭐ My places, schedules and alerts."),
    "🎯 Точность прогноза появится через день: бот начал записывать прогнозы на завтра для "
    "⭐ Моих мест, рассылок и предупреждений.": (
        "🎯 Точність прогнозу з'явиться через день: бот почав записувати прогнози на завтра для "
        "⭐ Моїх місць, розсилок і попереджень.",
        "🎯 Forecast accuracy will appear in a day: the bot has started logging next-day forecasts for "
        "⭐ My places, schedules and alerts."),
    "Фактическая погода — по данным Open-Meteo (модели с учётом наблюдений).": (
        "Фактична погода — за даними Open-Meteo (моделі з урахуванням спостережень).",
        "Actual weather is from Open-Meteo (models adjusted to observations)."),
})

# Справка /help и /start (ключ — core.HELP целиком)
T[(
    "Я показываю погоду 🌦\n"
    "\n"
    "• Просто напишите название города, например <i>Москва</i>, пришлю погоду, графики на сутки (температура, осадки, ветер, влажность), восход и заход солнца и луны, фазу луны\n"
    "• /week <i>город</i> то же на 7 дней\n"
    "• Или отправьте геолокацию кнопкой ниже\n"
    "\n"
    "Кнопки внизу:\n"
    "• {geo} — погода там, где вы сейчас\n"
    "• {now} и {week} — для последнего города или места\n"
    "• Под прогнозом: 🔄 Обновить (перерисует тот же прогноз), переключение сегодня/неделя и ⏱ По часам — 12 часов текстом\n"
    "• В сводке есть совет, что надеть 👕\n"
    "/weather и /week без города тоже показывают последнее место\n"
    "• Координаты текстом, например <code>51.18, 32.83</code>, — погода в этой точке\n"
    "• Если городов с таким названием несколько, предложу выбрать кнопками. Можно сразу уточнить через запятую: <i>Бахмач, Черниговская</i> или <i>Париж, США</i>\n"
    "\n"
    "{places} — ваш список мест (до {fav_limit}):\n"
    "• /add <i>город</i> или /add <i>широта долгота [название]</i> — добавить\n"
    "• /places — список, нажмите место, чтобы узнать погоду\n"
    "• /del <i>номер или название</i> — удалить\n"
    "• ⭐ В мои места — кнопка под прогнозом\n"
    "\n"
    "{date} — погода на любую дату (прогноз до 16 дней вперёд, архив с 1940 года):\n"
    "• /date <i>21.11</i> или <i>21.11.2026</i>, <i>завтра</i>, <i>вчера</i> [город или координаты]\n"
    "• 📆 Другая дата — кнопка под прогнозом\n"
    "\n"
    "{subs} — бот сам присылает погоду (до {sub_limit} рассылок):\n"
    "• /subscribe [город] — выбрать периодичность: каждый 1/3/6/12 ч, раз в сутки или в своё время\n"
    "• /subscribe <i>Бахмач 3ч</i> или <i>Бахмач 08:00, 20:00</i> — сразу\n"
    "• добавьте <i>кратко</i> — три строки без графиков (переключается и в /subs)\n"
    "• дни недели: <i>Бахмач по будням 07:30</i>, <i>сб вс 10:00</i>\n"
    "• условие: <i>Бахмач 07:00 если дождь</i> (снег, мороз, ниже -5, выше 25) — без осадков рассылка в этот день не придёт\n"
    "• /subs — ваши рассылки, /unsubscribe <i>номер</i> или <i>all</i> — отключить\n"
    "• 🔔 Подписаться — кнопка под прогнозом\n"
    "\n"
    "{alerts} или /alerts — бот сам напишет, если ожидается заморозок, гроза, порывы ветра от 15 м/с, жара, сильный мороз, резкий перепад температуры или осадки через 1–2 часа (ночью с 23 до 7 молчит). До {alert_limit} мест, каждое предупреждение включается отдельно\n"
    "\n"
    "Ещё:\n"
    "• /air [город] или 🌫 Воздух под прогнозом — качество воздуха (индекс EAQI, PM2.5, PM10) и пыльца\n"
    "• /weekend [город] или 🏖 Выходные — прогноз на ближайшие субботу и воскресенье с советом\n"
    "• /table [город] или 📋 Таблица — 3 дня текстом: утро, день, вечер и ночь\n"
    "• /compare или 📊 Сравнить в «Моих местах» — все места в одном сообщении и на одном графике\n"
    "• /radar [город] или 🛰 Радар — снимок радара осадков (RainViewer) и когда начнётся или закончится дождь в ближайшие 3 часа\n"
    "• /models [город] или 🧪 Модели — ECMWF, ICON и GFS (и OpenWeatherMap, если задан ключ) на одном графике: где модели расходятся, прогноз менее надёжен\n"
    "• /review [город] или 📈 Итоги недели — погода за прошедшие 7 дней и насколько точным был прогноз на завтра. По воскресеньям в 20:00 бот присылает итоги сам (отключается в настройках)\n"
    "• В сводке на сегодня и на дату есть строка 📈 «как обычно в этот день» — норма за 1991–2020\n"
    "\n"
    "Кроме городов можно искать горы, станции, озёра и достопримечательности: «Говерла», «озеро Свитязь»\n"
    "\n"
    "{settings} или /settings — язык (русский, українська, English), модель прогноза (Авто, ECMWF, ICON, GFS), источник качества воздуха (Open-Meteo, станции WAQI или выключено), что показывать в краткой сводке рассылок и итоги недели\n"
    "\n"
    "{ping} или /ping — проверить связь: сервер бота, Telegram, Open-Meteo, рассылки"
)] = (
    (
        "Я показую погоду 🌦\n"
        "\n"
        "• Просто напишіть назву міста, наприклад <i>Київ</i>, надішлю погоду, графіки на добу (температура, опади, вітер, вологість), схід і захід сонця та місяця, фазу місяця\n"
        "• /week <i>місто</i> те саме на 7 днів\n"
        "• Або надішліть геолокацію кнопкою нижче\n"
        "\n"
        "Кнопки внизу:\n"
        "• {geo} — погода там, де ви зараз\n"
        "• {now} і {week} — для останнього міста чи місця\n"
        "• Під прогнозом: 🔄 Оновити (перемалює той самий прогноз), перемикання сьогодні/тиждень і ⏱ По годинах — 12 годин текстом\n"
        "• У зведенні є порада, що вдягнути 👕\n"
        "/weather і /week без міста теж показують останнє місце\n"
        "• Координати текстом, наприклад <code>51.18, 32.83</code>, — погода в цій точці\n"
        "• Якщо міст із такою назвою кілька, запропоную обрати кнопками. Можна одразу уточнити через кому: <i>Бахмач, Чернігівська</i> або <i>Париж, США</i>\n"
        "\n"
        "{places} — ваш список місць (до {fav_limit}):\n"
        "• /add <i>місто</i> або /add <i>широта довгота [назва]</i> — додати\n"
        "• /places — список, натисніть місце, щоб дізнатися погоду\n"
        "• /del <i>номер або назва</i> — видалити\n"
        "• ⭐ До моїх місць — кнопка під прогнозом\n"
        "\n"
        "{date} — погода на будь-яку дату (прогноз до 16 днів уперед, архів з 1940 року):\n"
        "• /date <i>21.11</i> або <i>21.11.2026</i>, <i>завтра</i>, <i>вчора</i> [місто або координати]\n"
        "• 📆 Інша дата — кнопка під прогнозом\n"
        "\n"
        "{subs} — бот сам надсилає погоду (до {sub_limit} розсилок):\n"
        "• /subscribe [місто] — обрати періодичність: кожні 1/3/6/12 год, раз на добу або у свій час\n"
        "• /subscribe <i>Бахмач 3год</i> або <i>Бахмач 08:00, 20:00</i> — одразу\n"
        "• додайте <i>коротко</i> — три рядки без графіків (перемикається й у /subs)\n"
        "• дні тижня: <i>Бахмач по буднях 07:30</i>, <i>сб нд 10:00</i>\n"
        "• умова: <i>Бахмач 07:00 якщо дощ</i> (сніг, мороз, нижче -5, вище 25) — без опадів розсилка цього дня не прийде\n"
        "• /subs — ваші розсилки, /unsubscribe <i>номер</i> або <i>all</i> — вимкнути\n"
        "• 🔔 Підписатися — кнопка під прогнозом\n"
        "\n"
        "{alerts} або /alerts — бот сам напише, якщо очікується заморозок, гроза, пориви вітру від 15 м/с, спека, сильний мороз, різкий перепад температури або опади за 1–2 години (вночі з 23 до 7 мовчить). До {alert_limit} місць, кожне попередження вмикається окремо\n"
        "\n"
        "Ще:\n"
        "• /air [місто] або 🌫 Повітря під прогнозом — якість повітря (індекс EAQI, PM2.5, PM10) і пилок\n"
        "• /weekend [місто] або 🏖 Вихідні — прогноз на найближчі суботу й неділю з порадою\n"
        "• /table [місто] або 📋 Таблиця — 3 дні текстом: ранок, день, вечір і ніч\n"
        "• /compare або 📊 Порівняти в «Моїх місцях» — усі місця в одному повідомленні й на одному графіку\n"
        "• /radar [місто] або 🛰 Радар — знімок радара опадів (RainViewer) і коли почнеться чи закінчиться дощ найближчі 3 години\n"
        "• /models [місто] або 🧪 Моделі — ECMWF, ICON і GFS (і OpenWeatherMap, якщо задано ключ) на одному графіку: де моделі розходяться, прогноз менш надійний\n"
        "• /review [місто] або 📈 Підсумки тижня — погода за минулі 7 днів і наскільки точним був прогноз на завтра. Щонеділі о 20:00 бот надсилає підсумки сам (вимикається в налаштуваннях)\n"
        "• У зведенні на сьогодні й на дату є рядок 📈 «як зазвичай цього дня» — норма за 1991–2020\n"
        "\n"
        "Крім міст можна шукати гори, станції, озера й пам'ятки: «Говерла», «озеро Світязь»\n"
        "\n"
        "{settings} або /settings — мова (русский, українська, English), модель прогнозу (Авто, ECMWF, ICON, GFS), джерело якості повітря (Open-Meteo, станції WAQI або вимкнено), що показувати в короткому зведенні розсилок і підсумки тижня\n"
        "\n"
        "{ping} або /ping — перевірити зв'язок: сервер бота, Telegram, Open-Meteo, розсилки"
    ),
    (
        "I show the weather 🌦\n"
        "\n"
        "• Just type a city name, e.g. <i>Kyiv</i>, and I'll send the weather, 24-hour charts (temperature, precipitation, wind, humidity), sunrise and sunset, moonrise and moonset, and the moon phase\n"
        "• /week <i>city</i> — the same for 7 days\n"
        "• Or send your location with the button below\n"
        "\n"
        "Buttons below:\n"
        "• {geo} — the weather where you are now\n"
        "• {now} and {week} — for your last city or place\n"
        "• Under a forecast: 🔄 Refresh (redraws the same forecast), today/week switch and ⏱ Hourly — the next 12 hours as text\n"
        "• The summary includes a tip on what to wear 👕\n"
        "/weather and /week without a city also show your last place\n"
        "• Coordinates as text, e.g. <code>51.18, 32.83</code>, — the weather at that point\n"
        "• If several cities share a name, I'll offer buttons to choose. You can narrow it down after a comma: <i>Bakhmach, Chernihiv</i> or <i>Paris, US</i>\n"
        "\n"
        "{places} — your list of places (up to {fav_limit}):\n"
        "• /add <i>city</i> or /add <i>latitude longitude [name]</i> — add\n"
        "• /places — the list, tap a place to get its weather\n"
        "• /del <i>number or name</i> — remove\n"
        "• ⭐ Save place — a button under a forecast\n"
        "\n"
        "{date} — the weather for any date (forecast up to 16 days ahead, archive since 1940):\n"
        "• /date <i>21.11</i> or <i>21.11.2026</i>, <i>tomorrow</i>, <i>yesterday</i> [city or coordinates]\n"
        "• 📆 Another date — a button under a forecast\n"
        "\n"
        "{subs} — the bot sends you the weather by itself (up to {sub_limit} schedules):\n"
        "• /subscribe [city] — choose how often: every 1/3/6/12 h, once a day or at your own time\n"
        "• /subscribe <i>Kyiv 3h</i> or <i>Kyiv 08:00, 20:00</i> — right away\n"
        "• add <i>short</i> — three lines without charts (also switchable in /subs)\n"
        "• days of the week: <i>Kyiv weekdays 07:30</i>, <i>sat sun 10:00</i>\n"
        "• condition: <i>Kyiv 07:00 if rain</i> (snow, frost, below -5, above 25) — with no precipitation there's no message that day\n"
        "• /subs — your schedules, /unsubscribe <i>number</i> or <i>all</i> — turn off\n"
        "• 🔔 Subscribe — a button under a forecast\n"
        "\n"
        "{alerts} or /alerts — the bot messages you about expected frost, thunderstorms, wind gusts from 15 m/s, heat, severe cold, a sharp temperature swing or precipitation in 1–2 hours (quiet at night from 23 to 7). Up to {alert_limit} places, each alert type is switched separately\n"
        "\n"
        "More:\n"
        "• /air [city] or 🌫 Air under a forecast — air quality (EAQI index, PM2.5, PM10) and pollen\n"
        "• /weekend [city] or 🏖 Weekend — the forecast for the coming Saturday and Sunday with advice\n"
        "• /table [city] or 📋 Table — 3 days as text: morning, day, evening and night\n"
        "• /compare or 📊 Compare in “My places” — all places in one message and on one chart\n"
        "• /radar [city] or 🛰 Radar — a precipitation radar image (RainViewer) and when rain will start or stop in the next 3 hours\n"
        "• /models [city] or 🧪 Models — ECMWF, ICON and GFS (and OpenWeatherMap if a key is set) on one chart: where models disagree, the forecast is less reliable\n"
        "• /review [city] or 📈 Week in review — the past 7 days' weather and how accurate the next-day forecast was. On Sundays at 20:00 the bot sends the review by itself (can be turned off in settings)\n"
        "• Today's and date summaries include a 📈 “normal for this day” line — the 1991–2020 average\n"
        "\n"
        "Besides cities you can search for mountains, stations, lakes and landmarks: “Hoverla”, “Svitiaz lake”\n"
        "\n"
        "{settings} or /settings — language (русский, українська, English), forecast model (Auto, ECMWF, ICON, GFS), air quality source (Open-Meteo, WAQI stations or off), what to show in short scheduled summaries, and the week in review\n"
        "\n"
        "{ping} or /ping — check the connection: bot server, Telegram, Open-Meteo, schedules"
    ),
)
