"""Предупреждения о погоде: бот сам пишет, когда ожидается заморозок, гроза, сильный ветер и т. п.

Проверка идёт в фоне раз в CHECK_EVERY; одно и то же событие отправляется один раз (ключ события
хранится в "sent"), ночью (QUIET_FROM–QUIET_TO по местному времени места) бот молчит.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from advice import is_wet, upcoming
from i18n import N_, _
from weather import Place

CHECK_EVERY = timedelta(minutes=30)
ALERT_LIMIT = 5          # мест с предупреждениями на пользователя
QUIET_FROM, QUIET_TO = 23, 7
STORM_CODES = {95, 96, 99}
FROST_C, HEAT_C, COLD_C = -0.5, 30, -20
GUST_MS, JUMP_C = 15, 8

KINDS = {  # код → подпись кнопки
    "frost": N_("❄️ Заморозок"),
    "rain": N_("☔️ Осадки через 1–2 ч"),
    "storm": N_("⛈ Гроза"),
    "wind": N_("💨 Ветер от 15 м/с"),
    "heat": N_("🔥 Жара от +30°"),
    "cold": N_("🥶 Мороз от −20°"),
    "jump": N_("🌡 Перепад от 8°"),
}


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else ("−" + str(-t) if t < 0 else "0")


def detect(data: dict) -> list[tuple[str, str, str]]:
    """События в данных прогноза: [(вид, ключ для повторов, текст)]."""
    cur = data.get("current") or {}
    hours = upcoming(data, 24)
    if not hours or cur.get("temperature_2m") is None:
        return []
    found = []
    temps = [(h["temp"], h) for h in hours if h["temp"] is not None]

    night = [(t, h) for t, h in temps[:18]]
    if night and cur["temperature_2m"] > 0:
        t, h = min(night, key=lambda x: x[0])
        if t <= FROST_C:
            found.append(("frost", f"frost:{h['time'][:10]}",
                          _("❄️ Заморозок: до {t}°C около {at}", t=_deg(t), at=h['time'][11:16])))

    wet_now = (cur.get("precipitation") or 0) >= 0.1 or is_wet(hours[0])
    soon = next((h for h in hours[1:3] if is_wet(h)), None)
    if soon and not wet_now:
        prob = _(" (вероятность {p}%)", p=soon['prob']) if soon["prob"] is not None else ""
        snow = soon["code"] in {71, 73, 75, 77, 85, 86}
        text = (_("🌨 Снег начнётся около {at}{prob}", at=soon['time'][11:16], prob=prob) if snow else
                _("☔️ Дождь начнётся около {at}{prob}", at=soon['time'][11:16], prob=prob))
        found.append(("rain", f"rain:{soon['time'][:13]}", text))

    storm = next((h for h in hours[:12] if h["code"] in STORM_CODES), None)
    if storm:
        found.append(("storm", f"storm:{storm['time'][:10]}", _("⛈ Гроза около {at}", at=storm['time'][11:16])))

    gusts = [h for h in hours[:12] if (h["gust"] or 0) >= GUST_MS]
    if gusts:
        g = max(gusts, key=lambda h: h["gust"])
        found.append(("wind", f"wind:{g['time'][:10]}",
                      _("💨 Порывы ветра до {g} м/с около {at}", g=round(g['gust']), at=g['time'][11:16])))

    if temps:
        t, h = max(temps, key=lambda x: x[0])
        if t >= HEAT_C:
            found.append(("heat", f"heat:{h['time'][:10]}",
                          _("🔥 Жара до {t}°C около {at}", t=_deg(t), at=h['time'][11:16])))
        t, h = min(temps, key=lambda x: x[0])
        if t <= COLD_C:
            found.append(("cold", f"cold:{h['time'][:10]}",
                          _("🥶 Мороз до {t}°C около {at}", t=_deg(t), at=h['time'][11:16])))

    d = data.get("daily") or {}
    days, tmax = d.get("time") or [], d.get("temperature_2m_max") or []
    if len(days) >= 2 and len(tmax) >= 2 and None not in tmax[:2]:
        diff = round(tmax[1] - tmax[0])
        if abs(diff) >= JUMP_C:
            text = (_("🌡 Завтра на {n}° теплее: днём до {t}°C", n=diff, t=_deg(tmax[1])) if diff > 0 else
                    _("🌡 Завтра на {n}° холоднее: днём до {t}°C", n=-diff, t=_deg(tmax[1])))
            found.append(("jump", f"jump:{days[1]}", text))
    return found


def quiet(data: dict) -> bool:
    """Ночь по местному времени места (current.time уже местное)."""
    t = (data.get("current") or {}).get("time", "")
    if len(t) < 13:
        return False
    h = int(t[11:13])
    return h >= QUIET_FROM or h < QUIET_TO


class Alerts:
    """user_id → [{id, name, lat, lon, kinds: [...], sent: {ключ: время UTC}}]; хранится в JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): [a for a in v if isinstance(a, dict) and {"id", "lat", "lon"} <= a.keys()]
                          for k, v in raw.items() if isinstance(v, list)}
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    def list(self, user_id: int) -> list[dict]:
        return list(self._data.get(str(user_id), []))

    def get(self, user_id: int, alert_id: int) -> dict | None:
        return next((a for a in self._data.get(str(user_id), []) if a["id"] == alert_id), None)

    def find(self, user_id: int, lat: float, lon: float) -> dict | None:
        return next((a for a in self._data.get(str(user_id), [])
                     if round(a["lat"], 3) == round(lat, 3) and round(a["lon"], 3) == round(lon, 3)), None)

    def add(self, user_id: int, place: Place) -> dict | None:
        """Место с предупреждениями (все виды включены); то же место — вернуть как есть; None — лимит."""
        found = self.find(user_id, place.lat, place.lon)
        if found:
            return found
        items = self._data.setdefault(str(user_id), [])
        if len(items) >= ALERT_LIMIT:
            return None
        a = {"id": max((x["id"] for x in items), default=0) + 1, "name": place.name,
             "lat": place.lat, "lon": place.lon, "kinds": list(KINDS), "sent": {}}
        items.append(a)
        self._save()
        return a

    def toggle(self, user_id: int, alert_id: int, kind: str) -> dict | None:
        a = self.get(user_id, alert_id)
        if not a or kind not in KINDS:
            return None
        kinds = a.setdefault("kinds", [])
        if kind in kinds:
            kinds.remove(kind)
        else:
            kinds.append(kind)
        self._save()
        return a

    def remove(self, user_id: int, alert_id: int) -> dict | None:
        items = self._data.get(str(user_id), [])
        for i, a in enumerate(items):
            if a["id"] == alert_id:
                items.pop(i)
                self._save()
                return a
        return None

    def remove_all(self, user_id: int) -> int:
        n = len(self._data.pop(str(user_id), []))
        if n:
            self._save()
        return n

    def all(self) -> list[tuple[int, dict]]:
        return [(int(uid), a) for uid, items in self._data.items() for a in items if a.get("kinds")]

    def new_events(self, alert: dict, events: list[tuple[str, str, str]], now: datetime) -> list[str]:
        """Тексты событий, которые ещё не отправлялись; заодно помечает их отправленными.

        Осадки не чаще раза в 3 часа, остальное — один раз на ключ (обычно на дату).
        """
        sent = alert.setdefault("sent", {})
        for key, at in list(sent.items()):  # старые ключи не нужны
            if datetime.fromisoformat(at) < now - timedelta(days=3):
                del sent[key]
        texts = []
        for kind, key, text in events:
            if kind not in alert.get("kinds", []) or key in sent:
                continue
            if kind == "rain" and any(k.startswith("rain:") and datetime.fromisoformat(v) > now - timedelta(hours=3)
                                      for k, v in sent.items()):
                continue
            sent[key] = now.astimezone(timezone.utc).isoformat()
            texts.append(text)
        if texts:
            self._save()
        return texts

    @staticmethod
    def place(alert: dict) -> Place:
        return Place(alert["name"], float(alert["lat"]), float(alert["lon"]))


async def check_all(alerts: Alerts, fetch, send, now: datetime, blocked_exc: tuple = (),
                    model_of=lambda uid: None) -> int:
    """Проверить все места. fetch(place) → data, send(user_id, alert, texts) — корутины.

    Всё для места — запрос, тексты событий и отправка — идёт от имени владельца (prefs.current_user):
    так берутся его модель прогноза и язык.
    """
    from prefs import current_user

    sent = 0
    cache: dict[tuple, dict] = {}  # одно место и модель у нескольких пользователей — один запрос
    for uid, alert in alerts.all():
        key = (model_of(uid), round(alert["lat"], 2), round(alert["lon"], 2))
        token = current_user.set(uid)
        try:
            if key not in cache:
                cache[key] = await fetch(Alerts.place(alert))
            data = cache[key]
            if quiet(data):
                continue
            texts = alerts.new_events(alert, detect(data), now)
            if texts:
                await send(uid, alert, texts)
                sent += 1
        except blocked_exc:
            logging.info("пользователь %s заблокировал бота — удаляю предупреждения", uid)
            alerts.remove_all(uid)
        except Exception:
            logging.exception("ошибка проверки предупреждений для %s", uid)
        finally:
            current_user.reset(token)
    return sent

