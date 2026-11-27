"""Предупреждения о погоде: бот сам пишет, когда ожидается заморозок, гроза, гололёд, сильный ветер и т. п.

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
FREEZING_CODES = {56, 57, 66, 67}   # ледяная морось и ледяной дождь
FOG_CODES = {45, 48}
FOG_VIS_M = 500                     # видимость меньше — туман
SNOW_CM = 5                         # снегопад: столько см и больше за 12 ч
ICE_WET_MM, ICE_COLD_C = 0.1, -1    # мокро при плюсе, а потом мороз до −1° и ниже → гололедица
CHANGE_C, CHANGE_MM = 5, 1.0        # «прогноз изменился»: на 5° и больше или появились/пропали осадки от 1 мм
PRESSURE_MM = 7                     # давление меняется на 7 мм рт. ст. и больше за сутки
PROMISE_FROM = 18                   # с 18:00 по местному времени запоминаем прогноз на завтра

KINDS = {  # код → подпись кнопки
    "frost": N_("❄️ Заморозок"),
    "rain": N_("☔️ Осадки через 1–2 ч"),
    "storm": N_("⛈ Гроза"),
    "wind": N_("💨 Ветер от 15 м/с"),
    "heat": N_("🔥 Жара от +30°"),
    "cold": N_("🥶 Мороз от −20°"),
    "jump": N_("🌡 Перепад от 8°"),
    "ice": N_("🧊 Гололёд"),
    "snow": N_("🌨 Снегопад от 5 см"),
    "fog": N_("🌫 Туман"),
    "change": N_("🔄 Прогноз изменился"),
    "pressure": N_("🧭 Скачок давления"),
    "magnet": N_("🧲 Магнитная буря"),
}
OLD_KINDS = ("frost", "rain", "storm", "wind", "heat", "cold", "jump")  # были до зимних; новые включаются сами


def _deg(t: float) -> str:
    t = round(t)
    return f"+{t}" if t > 0 else ("−" + str(-t) if t < 0 else "0")


def detect(data: dict, kp: list | None = None, now: datetime | None = None) -> list[tuple[str, str, str]]:
    """События в данных прогноза: [(вид, ключ для повторов, текст)]. kp — прогноз NOAA (geomag.parse)."""
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

    found += _winter(hours)
    found += _pressure(data)
    import geomag

    storm = geomag.for_data(kp, data, now)
    if storm and storm["level"]:
        found.append(("magnet", f"magnet:{storm['day']}", geomag.text(storm)))

    d = data.get("daily") or {}
    days, tmax = d.get("time") or [], d.get("temperature_2m_max") or []
    if len(days) >= 2 and len(tmax) >= 2 and None not in tmax[:2]:
        diff = round(tmax[1] - tmax[0])
        if abs(diff) >= JUMP_C:
            text = (_("🌡 Завтра на {n}° теплее: днём до {t}°C", n=diff, t=_deg(tmax[1])) if diff > 0 else
                    _("🌡 Завтра на {n}° холоднее: днём до {t}°C", n=-diff, t=_deg(tmax[1])))
            found.append(("jump", f"jump:{days[1]}", text))
    return found


def _winter(hours: list[dict]) -> list[tuple[str, str, str]]:
    """Гололёд, сильный снегопад и туман в ближайшие часы."""
    found = []
    freezing = next((h for h in hours[:18] if h["code"] in FREEZING_CODES), None)
    if freezing:
        found.append(("ice", f"ice:{freezing['time'][:10]}",
                      _("🧊 Ледяной дождь около {at} — на дорогах гололёд", at=freezing['time'][11:16])))
    else:
        for i, h in enumerate(hours[:18]):
            if (h["prec"] or 0) < ICE_WET_MM or h["temp"] is None or h["temp"] < 0:
                continue
            cold = next((c for c in hours[i + 1:i + 7] if c["temp"] is not None and c["temp"] <= ICE_COLD_C), None)
            if cold:
                found.append(("ice", f"ice:{cold['time'][:10]}",
                              _("🧊 Гололедица: после осадков к {at} похолодает до {t}°C",
                                at=cold['time'][11:16], t=_deg(cold['temp']))))
                break

    snowy = [h for h in hours[:12] if (h.get("snow") or 0) > 0]
    total = sum(h["snow"] for h in snowy)
    if total >= SNOW_CM:
        found.append(("snow", f"snow:{snowy[0]['time'][:10]}",
                      _("🌨 Сильный снег: около {n} см за 12 ч, начало около {at}",
                        n=round(total), at=snowy[0]['time'][11:16])))

    fog = next((h for h in hours[:12] if h["code"] in FOG_CODES
                or (h.get("vis") is not None and h["vis"] < FOG_VIS_M)), None)
    if fog:
        text = _("🌫 Туман около {at}", at=fog['time'][11:16])
        if fog.get("vis") is not None and fog["vis"] < 1000:
            text += _(", видимость до {m} м", m=max(50, round(fog["vis"], -1)))
        found.append(("fog", f"fog:{fog['time'][:10]}", text))
    return found


def day_forecast(data: dict, i: int) -> dict | None:
    """День i из daily (0 — сегодня, 1 — завтра): {day, tmax, tmin, prec} или None."""
    d = data.get("daily") or {}
    days = d.get("time") or []

    def at(name):
        col = d.get(name) or []
        return col[i] if len(col) > i else None

    if len(days) <= i or at("temperature_2m_max") is None or at("temperature_2m_min") is None:
        return None
    return {"day": days[i], "tmax": at("temperature_2m_max"), "tmin": at("temperature_2m_min"),
            "prec": at("precipitation_sum") or 0.0}


def _pressure(data: dict) -> list[tuple[str, str, str]]:
    from weather import pressure_change

    ch = pressure_change(data, 24)
    if not ch or abs(ch[1]) < PRESSURE_MM:
        return []
    p, d, at = ch
    day = (data.get("current") or {}).get("time", "")[:10]
    text = (_("🧭 Давление резко падает: на {d} мм рт. ст. за сутки, к {at} до {p} мм", d=round(-d), at=at,
              p=round(p + d)) if d < 0 else
            _("🧭 Давление резко растёт: на {d} мм рт. ст. за сутки, к {at} до {p} мм", d=round(d), at=at,
              p=round(p + d)))
    return [("pressure", f"pressure:{day}", text)]


def promise(data: dict) -> dict | None:
    """Прогноз на завтра — вечером запоминаем, утром сверяем."""
    return day_forecast(data, 1)


def _summary(v: dict) -> str:
    rain = _(", осадки {mm} мм", mm=max(1, round(v["prec"]))) if v["prec"] >= CHANGE_MM else _(", без осадков")
    return f"{_deg(v['tmin'])}…{_deg(v['tmax'])}°{rain}"


def changed(data: dict, promised: dict | None) -> list[tuple[str, str, str]]:
    """Сегодняшний прогноз сильно разошёлся с тем, что вчера вечером обещали на сегодня."""
    now = day_forecast(data, 0)
    if not promised or not now or promised.get("day") != now["day"]:
        return []
    temp = max(abs(now["tmax"] - promised["tmax"]), abs(now["tmin"] - promised["tmin"]))
    wet_was, wet_now = promised["prec"] >= CHANGE_MM, now["prec"] >= CHANGE_MM
    rain_flip = wet_was != wet_now and abs(now["prec"] - promised["prec"]) >= CHANGE_MM
    if temp < CHANGE_C and not rain_flip:
        return []
    return [("change", f"change:{now['day']}",
             _("🔄 Прогноз на сегодня изменился: вчера вечером обещали {old}, теперь {new}",
               old=_summary(promised), new=_summary(now)))]


def local_hour(data: dict) -> int | None:
    t = (data.get("current") or {}).get("time", "")
    return int(t[11:13]) if len(t) >= 13 else None


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
        if self._add_new_kinds():
            self._save()

    def _add_new_kinds(self) -> bool:
        """Виды, которых не было, когда место добавляли (например, зимние), включить сами."""
        changed = False
        for items in self._data.values():
            for a in items:
                known = a.get("known") or OLD_KINDS
                new = [k for k in KINDS if k not in known]
                if new:
                    kinds = a.setdefault("kinds", [])
                    kinds += [k for k in new if k not in kinds]
                    a["known"] = list(KINDS)
                    changed = True
        return changed

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
             "lat": place.lat, "lon": place.lon, "kinds": list(KINDS), "known": list(KINDS), "sent": {}}
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

    def remember(self, alert: dict, data: dict) -> None:
        """Вечером запомнить прогноз на завтра — утром сверить его со свежим (вид «change»)."""
        hour = local_hour(data)
        p = promise(data) if hour is not None and hour >= PROMISE_FROM else None
        if p and alert.get("promise") != p:
            alert["promise"] = p
            self._save()

    @staticmethod
    def place(alert: dict) -> Place:
        return Place(alert["name"], float(alert["lat"]), float(alert["lon"]))


async def check_all(alerts: Alerts, fetch, send, now: datetime, blocked_exc: tuple = (),
                    model_of=lambda uid: None, kp: list | None = None) -> int:
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
            if "change" in alert.get("kinds", []):
                alerts.remember(alert, data)
            if quiet(data):
                continue
            texts = alerts.new_events(alert, detect(data, kp, now) + changed(data, alert.get("promise")), now)
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

