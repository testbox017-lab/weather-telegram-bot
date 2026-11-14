"""Разбор ответа геокодера Open-Meteo: одноимённые города и выбор между ними."""
from weather import Place

MAX_CHOICES = 8          # столько вариантов показываем кнопками
BIG_CITY = 100_000       # крупный город выбираем сразу…
BIG_RATIO = 20           # …если он в 20+ раз больше любого другого варианта


def _norm(s: str | None) -> str:
    return (s or "").casefold().replace("ё", "е").replace("-", " ").strip()


def split_query(query: str) -> tuple[str, str]:
    """«Бахмач, Черниговская» → ("Бахмач", "Черниговская"): уточнение региона или страны."""
    name, _, hint = (query or "").partition(",")
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
