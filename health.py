"""Проверка связи (/ping): сервер бота, Telegram, Open-Meteo, рассылки — с замером времени."""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

STARTED = datetime.now(timezone.utc)
SLOW_MS = 2000          # дольше — «медленно»
TICK_STALE = 120        # планировщик считается живым, если «тикал» не позже 2 минут назад
last_tick: datetime | None = None   # обновляется планировщиком рассылок


def mark_tick(now: datetime | None = None) -> None:
    global last_tick
    last_tick = now or datetime.now(timezone.utc)


@dataclass
class Check:
    name: str
    ok: bool
    ms: int
    detail: str = ""


async def measure(name: str, coro_factory, timeout: float = 5) -> Check:
    """Выполнить проверку с таймаутом и замерить время; ошибки не пробрасываются.

    coro_factory() может вернуть строку — она покажется как подробность (например, HTTP 200).
    """
    t0 = time.perf_counter()
    try:
        detail = await asyncio.wait_for(coro_factory(), timeout)
        return Check(name, True, round((time.perf_counter() - t0) * 1000), detail if isinstance(detail, str) else "")
    except asyncio.TimeoutError:
        return Check(name, False, round(timeout * 1000), "нет ответа")
    except Exception as e:  # noqa: BLE001 — показываем пользователю тип ошибки
        return Check(name, False, round((time.perf_counter() - t0) * 1000), str(e)[:60] or type(e).__name__)


def bot_version(env: dict | None = None, repo: Path | None = None) -> str:
    """Версия: GIT_COMMIT из окружения (Docker), иначе git rev-parse, иначе "dev"."""
    env = os.environ if env is None else env
    commit = (env.get("GIT_COMMIT") or "").strip()
    if commit and commit != "unknown":
        date = (env.get("GIT_DATE") or "").strip()
        return f"{commit} ({date})" if date else commit
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%h (%cd)", "--date=format:%d.%m.%Y"],
                             cwd=repo or Path(__file__).parent, capture_output=True, text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "dev"


class RateLimiter:
    """Не чаще одного раза в `seconds` для каждого пользователя."""

    def __init__(self, seconds: float = 10):
        self.seconds = seconds
        self._last: dict[int, float] = {}

    def wait_left(self, user_id: int, now: float | None = None) -> float:
        """0 — можно (и время запоминается), иначе сколько секунд подождать."""
        now = time.monotonic() if now is None else now
        prev = self._last.get(user_id)
        if prev is not None and now - prev < self.seconds:
            return self.seconds - (now - prev)
        self._last[user_id] = now
        return 0


def uptime(now: datetime, started: datetime = STARTED) -> str:
    sec = max(0, int((now - started).total_seconds()))
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} д {h} ч {m} мин"
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин" if m else f"{sec} с"


def _dot(ok: bool) -> str:
    return "🟢" if ok else "🔴"


def format_check(c: Check) -> str:
    if not c.ok:
        return f"🔴 {c.name}: ошибка — {c.detail}"
    extra = f"{c.detail}, " if c.detail else ""
    slow = " — медленно" if c.ms > SLOW_MS else ""
    return f"🟢 {c.name}: {extra}{c.ms} мс{slow}"


def format_report(checks: list[Check], now: datetime, *, version: str, subs_total: int,
                  next_send: datetime | None, tick: datetime | None, started: datetime = STARTED) -> str:
    sched_ok = tick is not None and (now - tick).total_seconds() < TICK_STALE
    all_ok = all(c.ok for c in checks) and sched_ok
    kyiv = now.astimezone(ZoneInfo("Europe/Kyiv"))
    lines = [
        "📡 <b>Связь в порядке</b>" if all_ok else "📡 <b>Есть проблемы со связью</b>",
        "",
        f"🟢 Сервер бота: работает, аптайм {uptime(now, started)}",
        f"     время {now:%H:%M:%S} UTC · {kyiv:%H:%M:%S} Киев ({now:%d.%m.%Y})",
        *[format_check(c) for c in checks],
    ]
    if sched_ok:
        line = f"🟢 Рассылки: работают, активных {subs_total}"
        if next_send:
            nk = next_send.astimezone(ZoneInfo("Europe/Kyiv"))
            line += f", ближайшая {nk:%d.%m %H:%M} (Киев)"
    else:
        line = f"🔴 Рассылки: планировщик не отвечает (активных {subs_total})"
    lines += [line, "", f"🏷 Версия бота: {version}"]
    return "\n".join(lines)
