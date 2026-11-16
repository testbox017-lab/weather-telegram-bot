"""Языки бота: русский (исходный), украинский и английский.

Тексты в коде пишутся по-русски и оборачиваются в _(): _("Ветер") или с подстановками
_("Ветер до {v:.1f} м/с", v=wind). Русская строка — ключ словаря переводов translations.T
(«русский»: («українська», "English"));
нет перевода — остаётся русский текст. Строки в константах (словари, списки) помечаются N_(),
а переводятся при показе: _(KINDS[k]). tests/test_i18n.py проверяет, что у каждой помеченной строки
есть перевод на оба языка и подстановки в переводе те же.

Язык берётся из настроек текущего пользователя (prefs, ключ "lang") через lang_hook — его задаёт core;
use("en") временно включает язык явно (тесты, служебные места).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

LANGS = {"ru": "Русский", "uk": "Українська", "en": "English"}
DEFAULT = "ru"

_forced: ContextVar[str | None] = ContextVar("lang_forced", default=None)
lang_hook = lambda: DEFAULT  # noqa: E731 — язык текущего пользователя; задаёт core


def _tables() -> dict[str, dict[str, str]]:
    from translations import T

    return {"uk": {k: v[0] for k, v in T.items()}, "en": {k: v[1] for k, v in T.items()}}


_cache: dict[str, dict[str, str]] | None = None


def table(code: str) -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = _tables()
    return _cache.get(code, {})


def lang() -> str:
    forced = _forced.get()
    if forced:
        return forced
    try:
        code = lang_hook()
    except Exception:  # настройки недоступны (например, в тестах без core) — русский
        code = DEFAULT
    return code if code in LANGS else DEFAULT


@contextmanager
def use(code: str):
    """Временно говорить на языке code (в этом контексте)."""
    token = _forced.set(code)
    try:
        yield
    finally:
        _forced.reset(token)


def tr(text: str, code: str) -> str:
    """Перевод русской строки на язык code (без подстановок)."""
    if code == DEFAULT or not text:
        return text
    return table(code).get(text, text)


def _(text: str, **kw) -> str:
    """Перевод на язык текущего пользователя; kw — подстановки в {…}."""
    out = tr(text, lang())
    return out.format(**kw) if kw else out


def N_(text: str) -> str:
    """Пометка «строка для перевода» в константах: переводится позже, при показе, через _()."""
    return text


def variants(text: str) -> set[str]:
    """Строка на всех языках: кнопки меню нужно узнавать, на каком бы языке их ни нажали."""
    return {tr(text, code) for code in LANGS}


WEEKDAYS = [N_("Пн"), N_("Вт"), N_("Ср"), N_("Чт"), N_("Пт"), N_("Сб"), N_("Вс")]


def wd(i: int) -> str:
    """Короткое название дня недели (0 — понедельник)."""
    return _(WEEKDAYS[i])


def geo_lang() -> str:
    """Язык названий мест для геокодеров Open-Meteo и OpenStreetMap."""
    return lang()


def wd_lower(i: int) -> str:
    """День недели внутри фразы: «до пт» по-русски и по-украински, «until Fri» по-английски."""
    text = wd(i)
    return text if lang() == "en" else text.lower()
