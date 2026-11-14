"""Графики погоды (PNG в память) на matplotlib."""
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # без окон, только рендер в файл
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

TEMP = "#e8590c"
TEMP_MIN = "#1c7ed6"
RAIN = "#74c0fc"
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _style(ax, title: str):
    ax.set_title(title, fontsize=13, loc="left", pad=10)
    ax.grid(axis="y", alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _next_hours(data: dict, hours: int):
    """Срез почасовых рядов, начиная с текущего часа: (времена, slice)."""
    times = [datetime.fromisoformat(t) for t in data["hourly"]["time"]]
    if "current" not in data:  # данные за выбранную дату — весь день с 00:00
        return times[:hours], slice(0, hours)
    now = datetime.fromisoformat(data["current"]["time"]).replace(minute=0)
    start = next((i for i, t in enumerate(times) if t >= now), 0)
    sl = slice(start, start + hours)
    return times[sl], sl


def hourly_chart(name: str, data: dict, hours: int = 24, title: str | None = None) -> bytes:
    """Температура (линия) и осадки (столбики): вероятность, %, или (в архиве) количество, мм."""
    h = data["hourly"]
    t, sl = _next_hours(data, hours)
    pairs = [(x, v) for x, v in zip(t, h["temperature_2m"][sl]) if v is not None]
    if not pairs:
        raise ValueError("нет почасовой температуры")
    probs = h.get("precipitation_probability")
    use_prob = bool(probs) and any(p is not None for p in probs[sl])
    rain = [p or 0 for p in (probs if use_prob else h.get("precipitation") or [0] * len(h["time"]))[sl]]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax2 = ax.twinx()
    ax2.bar(t, rain, width=1 / 26, color=RAIN, alpha=0.45)
    if use_prob:
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("Вероятность осадков, %", color="#4dabf7")
    else:
        ax2.set_ylim(0, max(max(rain, default=0) * 2.5, 2))
        ax2.set_ylabel("Осадки, мм", color="#4dabf7")
    t, temp = [x for x, _ in pairs], [v for _, v in pairs]
    ax2.spines["top"].set_visible(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)

    ax.plot(t, temp, color=TEMP, lw=2.5, marker="o", ms=3.5)
    for i in range(0, len(t), 3):
        ax.annotate(f"{round(temp[i])}°", (t[i], temp[i]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color=TEMP)
    lo, hi = min(temp), max(temp)
    ax.set_ylim(lo - 2, hi + 3)
    ax.set_ylabel("Температура, °C", color=TEMP)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    _style(ax, title or f"{name}: ближайшие {hours} ч")
    return _png(fig)


def daily_chart(name: str, data: dict, days: int = 7) -> bytes:
    """Мин/макс температура по дням (полоса между ними) и сумма осадков."""
    d = data["daily"]
    dates = [datetime.fromisoformat(x) for x in d["time"][:days]]
    tmax, tmin = d["temperature_2m_max"][:days], d["temperature_2m_min"][:days]
    rain = [x or 0 for x in d.get("precipitation_sum", [0] * days)[:days]]
    labels = [f"{DAYS_RU[x.weekday()]}\n{x:%d.%m}" for x in dates]
    xs = range(len(dates))

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax2 = ax.twinx()
    ax2.bar(xs, rain, width=0.5, color=RAIN, alpha=0.45)
    ax2.set_ylim(0, max(max(rain) * 2.5, 5))
    ax2.set_ylabel("Осадки, мм", color="#4dabf7")
    ax2.spines["top"].set_visible(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)

    ax.fill_between(xs, tmin, tmax, color=TEMP, alpha=0.12)
    ax.plot(xs, tmax, color=TEMP, lw=2.5, marker="o", label="Днём (макс.)")
    ax.plot(xs, tmin, color=TEMP_MIN, lw=2.5, marker="o", label="Ночью (мин.)")
    for i in xs:
        ax.annotate(f"{round(tmax[i])}°", (i, tmax[i]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color=TEMP)
        ax.annotate(f"{round(tmin[i])}°", (i, tmin[i]), textcoords="offset points",
                    xytext=(0, -15), ha="center", fontsize=9, color=TEMP_MIN)
    ax.set_ylim(min(tmin) - 4, max(tmax) + 4)
    ax.set_xticks(list(xs), labels)
    ax.set_ylabel("Температура, °C")
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
    _style(ax, f"{name}: прогноз на {len(dates)} дн.")
    return _png(fig)


WIND = "#2f9e44"
GUST = "#868e96"
HUM = "#1971c2"
COMPASS = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]


def compass(deg: float) -> str:
    """Направление, ОТКУДА дует ветер: 0° = северный."""
    return COMPASS[round(deg / 45) % 8]


def _clean(xs):
    return [0 if x is None else x for x in xs]


def wind_humidity_chart(name: str, data: dict, days: int = 1, hours: int = 24,
                        title: str | None = None) -> bytes:
    """Две панели: ветер (скорость, порывы, стрелки направления) и влажность.

    days == 1 — почасово на ближайшие сутки, иначе — по дням.
    """
    if days <= 1:
        h = data["hourly"]
        xs, sl = _next_hours(data, hours)
        speed, gust = _clean(h["wind_speed_10m"][sl]), _clean(h["wind_gusts_10m"][sl])
        direction = _clean(h["wind_direction_10m"][sl])
        hum = _clean(h["relative_humidity_2m"][sl])
        hum_lo = hum_hi = None
        step, labels = 3, None
        title = title or f"{name}: ветер и влажность, {hours} ч"
    else:
        d = data["daily"]
        dates = [datetime.fromisoformat(x) for x in d["time"][:days]]
        xs = list(range(len(dates)))
        speed = _clean(d["wind_speed_10m_max"][:days])
        gust = _clean(d["wind_gusts_10m_max"][:days])
        direction = _clean(d["wind_direction_10m_dominant"][:days])
        hum = _clean(d["relative_humidity_2m_mean"][:days])
        hum_lo = _clean(d.get("relative_humidity_2m_min", hum)[:days])
        hum_hi = _clean(d.get("relative_humidity_2m_max", hum)[:days])
        step = 1
        labels = [f"{DAYS_RU[x.weekday()]}\n{x:%d.%m}" for x in dates]
        title = title or f"{name}: ветер и влажность на {len(dates)} дн."

    fig, (aw, ah) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12})

    # --- ветер
    top = max(max(gust), max(speed), 1) * 1.6
    aw.fill_between(xs, speed, gust, color=GUST, alpha=0.12)
    aw.plot(xs, gust, color=GUST, lw=1.5, ls="--", label="Порывы")
    aw.plot(xs, speed, color=WIND, lw=2.5, marker="o", ms=3.5 if days <= 1 else 6,
            label="Ветер (макс.)" if days > 1 else "Ветер")
    aw.set_ylim(0, top)
    aw.set_ylabel("Ветер, м/с", color=WIND)
    row = top * 0.86
    for i in range(0, len(xs), step):
        # стрелка показывает, КУДА дует ветер (метео-направление + 180°)
        # «→» смотрит на восток (0°); азимут b соответствует повороту 90 - b
        aw.text(xs[i], row, "→", rotation=90 - (direction[i] + 180), rotation_mode="anchor",
                ha="center", va="center", fontsize=17, color="#495057")
        aw.annotate(f"{compass(direction[i])}\n{round(speed[i])}", (xs[i], row),
                    textcoords="offset points", xytext=(0, -32), ha="center",
                    fontsize=8, color="#495057")
    aw.legend(loc="upper left", frameon=False, fontsize=9, ncol=2, bbox_to_anchor=(0, 1.02))
    _style(aw, title)

    # --- влажность
    if hum_lo is not None:
        ah.fill_between(xs, hum_lo, hum_hi, color=HUM, alpha=0.12, label="Мин–макс")
    else:
        ah.fill_between(xs, 0, hum, color=HUM, alpha=0.10)
    ah.plot(xs, hum, color=HUM, lw=2.5, marker="o", ms=3.5 if days <= 1 else 6,
            label="Средняя" if days > 1 else None)
    for i in range(0, len(xs), step):
        ah.annotate(f"{round(hum[i])}%", (xs[i], hum[i]), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8, color=HUM)
    ah.set_ylim(0, 112)
    ah.set_yticks([0, 25, 50, 75, 100])
    ah.set_ylabel("Влажность, %", color=HUM)
    if hum_lo is not None:
        ah.legend(loc="lower left", frameon=False, fontsize=9, ncol=2)
    ah.grid(axis="y", alpha=0.3)
    for side in ("top", "right"):
        ah.spines[side].set_visible(False)

    if labels:
        ah.set_xticks(xs, labels)
    else:
        ah.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        ah.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    return _png(fig)
