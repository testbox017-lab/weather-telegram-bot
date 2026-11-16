"""Разбор ответа геокодера Open-Meteo: одноимённые города и выбор между ними."""
from i18n import N_, _
from weather import Place

MAX_CHOICES = 8          # столько вариантов показываем кнопками
BIG_CITY = 100_000       # крупный город выбираем сразу…
BIG_RATIO = 20           # …если он в 20+ раз больше любого другого варианта


def _norm(s: str | None) -> str:
    return (s or "").casefold().replace("ё", "е").replace("-", " ").strip()


def split_query(query: str) -> tuple[str, str]:
    """«Бахмач, Черниговская» → ("Бахмач", "Черниговская"): уточнение региона или страны."""
    name, _sep, hint = (query or "").partition(",")
    return name.strip(), hint.strip()


def _label(c: dict, with_admin2: bool = False) -> str:
    parts = [c.get("name"), c.get("admin2") if with_admin2 else None, c.get("admin1"), c.get("country")]
    return ", ".join(dict.fromkeys(p for p in parts if p))


def _matches_hint(c: dict, hint: str) -> bool:
    h = _norm(hint)
    return any(h in _norm(c.get(k)) for k in ("admin1", "admin2", "admin3", "country", "country_code"))


def candidates(results: list[dict], query: str) -> tuple[list[Place], bool]:
    """Варианты мест и признак «можно выбрать сразу» (один вариант или явный крупный город).

    Сначала оставляет точные совпадения названия (геокодер возвращает и похожие), затем
    фильтрует по уточнению после запятой. Одинаковые подписи различает по району (admin2),
    а если и так совпадают — по координатам.
    """
    results = [c for c in results or [] if "latitude" in c and "longitude" in c]
    name, hint = split_query(query)
    exact = [c for c in results if _norm(c.get("name")) == _norm(name)]
    if exact:
        results = exact
    if hint:
        hinted = [c for c in results if _matches_hint(c, hint)]
        if hinted:
            results = hinted
    seen, uniq = set(), []
    for c in results:  # один и тот же пункт иногда приходит дважды
        key = (round(c["latitude"], 2), round(c["longitude"], 2))
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    uniq = uniq[:MAX_CHOICES]
    if not uniq:
        return [], False

    labels = [_label(c) for c in uniq]
    if len(set(labels)) < len(labels):
        labels = [_label(c, with_admin2=labels.count(lb) > 1) for c, lb in zip(uniq, labels)]
    for i, lb in enumerate(labels):
        if labels.count(lb) > 1:
            labels[i] = f"{lb} ({uniq[i]['latitude']:.2f}, {uniq[i]['longitude']:.2f})"
    places = [Place(lb, c["latitude"], c["longitude"]) for c, lb in zip(uniq, labels)]

    if len(places) == 1:
        return places, True
    pops = [c.get("population") or 0 for c in uniq]
    top, rest = pops[0], max(pops[1:])
    obvious = top >= BIG_CITY and top >= BIG_RATIO * max(rest, 1)
    return places, obvious


# Тип объекта OpenStreetMap → подпись в скобках (города и сёла подписи не получают)
OSM_KINDS = {
    "peak": N_("вершина"), "volcano": N_("вулкан"), "mountain_range": N_("горы"), "ridge": N_("хребет"),
    "saddle": N_("перевал"), "station": N_("станция"), "halt": N_("станция"), "stop": N_("остановка"),
    "aerodrome": N_("аэропорт"), "lake": N_("озеро"), "reservoir": N_("водохранилище"), "water": N_("водоём"),
    "river": N_("река"), "bay": N_("залив"), "beach": N_("пляж"), "island": N_("остров"), "forest": N_("лес"),
    "wood": N_("лес"), "park": N_("парк"), "nature_reserve": N_("заповедник"), "national_park": N_("нацпарк"),
    "attraction": N_("достопримечательность"), "museum": N_("музей"), "castle": N_("замок"),
    "monument": N_("памятник"), "viewpoint": N_("смотровая площадка"), "camp_site": N_("кемпинг"),
    "alpine_hut": N_("приют"), "ski": N_("горнолыжный курорт"),
}


def osm_candidates(results: list[dict]) -> tuple[list[Place], bool]:
    """Варианты из Nominatim: «Говерла (вершина), Ивано-Франковская область, Украина»."""
    places, seen = [], set()
    for r in results or []:
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (round(lat, 2), round(lon, 2))
        if key in seen:
            continue
        seen.add(key)
        parts = [p.strip() for p in (r.get("display_name") or "").split(",") if p.strip()]
        parts = [p for p in parts if not p.replace(" ", "").replace("-", "").isdigit()]  # без почтовых индексов
        name = r.get("name") or (parts[0] if parts else f"{lat:.2f}, {lon:.2f}")
        kind = OSM_KINDS.get(r.get("type")) or OSM_KINDS.get(r.get("category"))
        tail = [p for p in parts[1:] if p != name][-2:]  # область и страна
        label = ", ".join([f"{name} ({_(kind)})" if kind else name] + tail)
        places.append(Place(label, lat, lon))
        if len(places) >= MAX_CHOICES:
            break
    return places, len(places) == 1


KIND_WORDS = {"озеро", "оз", "гора", "г", "река", "р", "вокзал", "станция", "ст", "пик", "вершина", "перевал",
              "водохранилище", "остров", "парк", "замок", "музей", "пляж", "лес",
              # по-украински и по-английски
              "річка", "станція", "острів", "водосховище", "ліс", "lake", "mount", "mt", "river", "station",
              "peak", "pass", "island", "park", "castle", "museum", "beach", "forest", "reservoir"}



def strip_kind_word(query: str) -> str | None:
    """«озеро Свитязь» → «Свитязь»; None, если в запросе нет такого слова."""
    words = (query or "").split()
    rest = [w for w in words if w.casefold().rstrip(".") not in KIND_WORDS]
    return " ".join(rest) if rest and len(rest) < len(words) else None
