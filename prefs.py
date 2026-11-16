"""Настройки пользователя: источник прогноза (модель Open-Meteo или OpenWeatherMap) и источник качества воздуха.

Текущий пользователь хранится в contextvar current_user: его ставит middleware для каждого
сообщения или кнопки, а рассылки и предупреждения — перед запросом погоды. Так клиент Open-Meteo
сам берёт нужную модель, и не надо протаскивать user_id через все функции.
"""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from pathlib import Path

from i18n import LANGS, N_

# Названия и пояснения переводятся при показе: _(title), _(about)
MODELS = {  # ключ Open-Meteo → (название, пояснение)
    "best_match": (N_("Авто"), N_("Open-Meteo сам выбирает самую точную модель для места.")),
    "ecmwf_ifs025": ("ECMWF", N_("Европейский центр прогнозов — одна из самых точных моделей в мире.")),
    "icon_seamless": ("ICON · DWD", N_("Немецкая служба погоды, подробная сетка для Европы.")),
    "gfs_seamless": ("GFS · NOAA", N_("Американская глобальная модель.")),
    "mean": (N_("Среднее"), N_("Среднее ECMWF, ICON, GFS (и OpenWeatherMap, если он подключён): "
                               "ошибки отдельных моделей сглаживаются. Погода словами, восход и УФ — от «Авто».")),
    "owm": ("OpenWeatherMap", N_("Независимый сервис со своим пересчётом моделей и наблюдений. Прогноз на 5 дней, "
                                 "дальше, а также восход и УФ — из Open-Meteo.")),
}
AIR_SOURCES = {
    "openmeteo": ("Open-Meteo · CAMS", N_("Модель Copernicus для любой точки: индекс EAQI и пыльца.")),
    "waqi": ("WAQI · aqicn.org", N_("Измерения ближайшей станции в пределах 5 км. Где станции рядом нет — "
                                    "не будет и значения.")),
    "off": (N_("Выключено"), N_("Кнопки и команды качества воздуха не будет.")),
}
REVIEW = {
    "on": (N_("По воскресеньям"), N_("Вечером в воскресенье — итоги недели для ⭐ Моих мест (до трёх).")),
    "off": (N_("Не присылать"), N_("Итоги можно посмотреть в любой момент: /review.")),
}
LANGUAGES = {code: (name, "") for code, name in LANGS.items()}  # названия языков — каждый на своём языке
DEFAULTS = {"lang": "ru", "model": "best_match", "air": "openmeteo", "review": "on"}
# поля краткой сводки (weather.SHORT_FIELDS) — список, хранится отдельно от выбора «одно из»
SHORT_KEY = "short"
CHOICES = {"lang": LANGUAGES, "model": MODELS, "air": AIR_SOURCES, "review": REVIEW}

current_user: ContextVar[int | None] = ContextVar("current_user", default=None)


class Prefs:
    """user_id → {"lang": ..., "model": ..., "air": ..., "review": ..., "short": [...]}; хранится в JSON-файле, по умолчанию — DEFAULTS."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): v for k, v in raw.items() if isinstance(v, dict)}
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def get(self, user_id: int | None) -> dict:
        from weather import SHORT_DEFAULT, SHORT_FIELDS

        saved = self._data.get(str(user_id), {}) if user_id is not None else {}
        out = {k: saved[k] if saved.get(k) in CHOICES[k] else v for k, v in DEFAULTS.items()}
        short = [f for f in saved.get(SHORT_KEY) or [] if f in SHORT_FIELDS]
        out[SHORT_KEY] = short or list(SHORT_DEFAULT)
        return out

    def set(self, user_id: int, key: str, value: str) -> bool:
        if value not in CHOICES.get(key, {}):
            return False
        self._data.setdefault(str(user_id), {})[key] = value
        self._save()
        return True

    def toggle_short(self, user_id: int, field: str) -> bool:
        """Включить или выключить поле краткой сводки. Последнее поле выключить нельзя → False."""
        from weather import SHORT_FIELDS

        if field not in SHORT_FIELDS:
            return False
        current = self.get(user_id)[SHORT_KEY]
        if field in current:
            if len(current) == 1:
                return False
            current.remove(field)
        else:
            current.append(field)
        self._data.setdefault(str(user_id), {})[SHORT_KEY] = [f for f in SHORT_FIELDS if f in current]
        self._save()
        return True

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    def current(self) -> dict:
        """Настройки пользователя, для которого сейчас идёт обработка."""
        return self.get(current_user.get())


def model_label(key: str) -> str:
    from i18n import _

    return _(MODELS.get(key, MODELS["best_match"])[0])

