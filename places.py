"""Память о последнем месте пользователя и данные для inline-кнопок."""
import json
import re
import logging
from pathlib import Path

from i18n import N_, _
from weather import Place

DEFAULT_NAME = N_("Выбранное место")  # переводится при показе: _(DEFAULT_NAME)


class LastPlaces:
    """Последнее место (name, lat, lon) каждого пользователя, хранится в JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): v for k, v in raw.items()
                          if isinstance(v, dict) and {"name", "lat", "lon"} <= v.keys()}
        except FileNotFoundError:
            self._data = {}
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)
            self._data = {}

    def save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, user_id: int) -> Place | None:
        v = self._data.get(str(user_id))
        return Place(v["name"], float(v["lat"]), float(v["lon"])) if v else None

    def set(self, user_id: int, place: Place) -> None:
        new = {"name": place.name, "lat": place.lat, "lon": place.lon}
        if self._data.get(str(user_id)) == new:
            return
        self._data[str(user_id)] = new
        try:
            self.save()
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)

    def name_for(self, user_id: int, lat: float, lon: float) -> str:
        """Имя места по координатам из кнопки, если это последнее место пользователя."""
        p = self.get(user_id)
        if p and round(p.lat, 3) == round(lat, 3) and round(p.lon, 3) == round(lon, 3):
            return p.name
        return _(DEFAULT_NAME)


def build_cb(days: int, lat: float, lon: float) -> str:
    """callback_data вида "w:1:55.756:37.617" (всегда ≤ 64 байт)."""
    return f"w:{days}:{lat:.3f}:{lon:.3f}"


def parse_cb(data: str | None) -> tuple[int, float, float] | None:
    """Обратное к build_cb; None для чужих/битых данных."""
    try:
        prefix, days, lat, lon = (data or "").split(":")
        days, lat, lon = int(days), float(lat), float(lon)
    except ValueError:
        return None
    if prefix != "w" or days not in (1, 7) or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return days, lat, lon


FAV_LIMIT = 20
_NUM = r"([-+]?\d{1,3}(?:[.,]\d+)?)"
_COORDS_RE = re.compile(rf"^\s*{_NUM}\s*[,;\s]\s*{_NUM}\s*(.*)$")


def parse_coords(text: str | None) -> tuple[float, float, str] | None:
    """«55.75, 37.61 Дача» / «55,75 37,61» → (lat, lon, имя или "")."""
    m = _COORDS_RE.match((text or "").strip())
    if not m:
        return None
    a, b, rest = m.groups()
    try:
        lat, lon = float(a.replace(",", ".")), float(b.replace(",", "."))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon, rest.strip(" ,;-—")[:40]


def coords_name(lat: float, lon: float) -> str:
    return _("Точка {lat:.2f}, {lon:.2f}", lat=lat, lon=lon)



class Favorites:
    """Избранные места пользователя (до FAV_LIMIT штук), хранятся в JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): [p for p in v if isinstance(p, dict) and {"name", "lat", "lon"} <= p.keys()]
                          for k, v in raw.items() if isinstance(v, list)}
        except FileNotFoundError:
            self._data = {}
        except Exception:
            logging.exception("не удалось прочитать %s", self.path)
            self._data = {}

    def save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def list(self, user_id: int) -> list[Place]:
        return [Place(p["name"], float(p["lat"]), float(p["lon"])) for p in self._data.get(str(user_id), [])]

    def find(self, user_id: int, lat: float, lon: float) -> int | None:
        for i, p in enumerate(self.list(user_id)):
            if round(p.lat, 3) == round(lat, 3) and round(p.lon, 3) == round(lon, 3):
                return i
        return None

    def find_name(self, user_id: int, name: str) -> int | None:
        name = name.strip().casefold()
        for i, p in enumerate(self.list(user_id)):
            if p.name.casefold() == name:
                return i
        return None

    def add(self, user_id: int, place: Place) -> str:
        """'added' | 'updated' (те же координаты или имя) | 'exists' (ничего не изменилось) | 'full'."""
        items = self._data.setdefault(str(user_id), [])
        new = {"name": place.name, "lat": place.lat, "lon": place.lon}
        i = self.find(user_id, place.lat, place.lon)
        if i is None:
            i = self.find_name(user_id, place.name)
        if i is not None:
            if items[i] == new:
                return "exists"
            items[i] = new
            self._save_safe()
            return "updated"
        if len(items) >= FAV_LIMIT:
            return "full"
        items.append(new)
        self._save_safe()
        return "added"

    def remove_by(self, user_id: int, key: str) -> Place | None:
        """Удаление по номеру (с 1) или по названию."""
        key = key.strip()
        if key.isdigit():
            return self.remove(user_id, int(key) - 1)
        i = self.find_name(user_id, key)
        return None if i is None else self.remove(user_id, i)

    def remove(self, user_id: int, index: int) -> Place | None:
        items = self._data.get(str(user_id), [])
        if not 0 <= index < len(items):
            return None
        p = items.pop(index)
        self._save_safe()
        return Place(p["name"], float(p["lat"]), float(p["lon"]))

    def _save_safe(self) -> None:
        try:
            self.save()
        except Exception:
            logging.exception("не удалось сохранить %s", self.path)
