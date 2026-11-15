import asyncio
from datetime import datetime, timedelta, timezone

import health
from health import Check, RateLimiter, bot_version, format_check, format_report, measure, uptime

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def test_uptime():
    assert uptime(NOW, NOW - timedelta(seconds=42)) == "42 с"
    assert uptime(NOW, NOW - timedelta(minutes=5)) == "5 мин"
    assert uptime(NOW, NOW - timedelta(hours=3, minutes=7)) == "3 ч 7 мин"
    assert uptime(NOW, NOW - timedelta(days=2, hours=1, minutes=30)) == "2 д 1 ч 30 мин"
    assert uptime(NOW, NOW + timedelta(seconds=5)) == "0 с"


def test_measure_ok_error_timeout():
    async def ok():
        return "HTTP 200"

    async def fail():
        raise ConnectionError("сеть недоступна")

    async def hang():
        await asyncio.sleep(10)

    r = asyncio.run(measure("A", ok))
    assert r.ok and r.detail == "HTTP 200" and r.ms >= 0
    r = asyncio.run(measure("B", fail))
    assert not r.ok and "сеть недоступна" in r.detail
    r = asyncio.run(measure("C", hang, timeout=0.05))
    assert not r.ok and r.detail == "нет ответа"


def test_format_check():
    assert format_check(Check("Telegram API", True, 120)) == "🟢 Telegram API: 120 мс"
    assert format_check(Check("Прогноз", True, 80, "HTTP 200")) == "🟢 Прогноз: HTTP 200, 80 мс"
    assert "медленно" in format_check(Check("X", True, 3000))
    assert format_check(Check("X", False, 5000, "нет ответа")) == "🔴 X: ошибка — нет ответа"


def test_format_report_all_ok():
    checks = [Check("Telegram API", True, 100), Check("Open-Meteo прогноз", True, 90, "HTTP 200")]
    t = format_report(checks, NOW, version="abc1234 (14.11.2026)", subs_total=2,
                      next_send=datetime(2026, 11, 15, 6, 0, tzinfo=timezone.utc),
                      tick=NOW - timedelta(seconds=20), started=NOW - timedelta(hours=1))
    assert t.startswith("📡 <b>Связь в порядке</b>")
    assert "аптайм 1 ч 0 мин" in t and "12:00:00 UTC" in t and "14:00:00 Киев" in t
    assert "🟢 Рассылки: работают, активных 2, ближайшая 15.11 08:00 (Киев)" in t
    assert "Версия бота: abc1234 (14.11.2026)" in t


def test_format_report_problems():
    checks = [Check("Telegram API", False, 5000, "нет ответа")]
    t = format_report(checks, NOW, version="dev", subs_total=0, next_send=None,
                      tick=NOW - timedelta(minutes=5))
    assert "Есть проблемы" in t and "🔴 Telegram API" in t and "планировщик не отвечает" in t
    t = format_report([], NOW, version="dev", subs_total=0, next_send=None, tick=None)
    assert "планировщик не отвечает" in t


def test_mark_tick():
    health.mark_tick(NOW)
    assert health.last_tick == NOW


def test_rate_limiter():
    rl = RateLimiter(10)
    assert rl.wait_left(1, now=100.0) == 0
    assert rl.wait_left(1, now=104.0) == 6
    assert rl.wait_left(2, now=104.0) == 0      # другой пользователь не ограничен
    assert rl.wait_left(1, now=110.0) == 0      # прошло 10 с — снова можно


def test_bot_version(tmp_path):
    assert bot_version({"GIT_COMMIT": "abc1234", "GIT_DATE": "14.11.2026"}) == "abc1234 (14.11.2026)"
    assert bot_version({"GIT_COMMIT": "abc1234"}) == "abc1234"
    # нет переменной и папка не git-репозиторий → "dev"
    assert bot_version({"GIT_COMMIT": "unknown"}, repo=tmp_path) == "dev"
    assert bot_version({}, repo=tmp_path) == "dev"


def test_heartbeat_file_and_problems(tmp_path):
    import time as _t
    p = tmp_path / "heartbeat.json"
    assert "нет файла" in health.heartbeat_problem(p, 1000)
    tick = datetime.fromtimestamp(990, timezone.utc)
    health.write_heartbeat(p, tick, True, None, now=1000)
    assert health.heartbeat_problem(p, 1010) is None
    assert "бот завис" in health.heartbeat_problem(p, 1000 + health.HEARTBEAT_STALE + 1)
    health.write_heartbeat(p, datetime.fromtimestamp(500, timezone.utc), True, None, now=1000)
    assert "планировщик" in health.heartbeat_problem(p, 1000)
    health.write_heartbeat(p, None, True, None, now=1000)
    assert "планировщик" in health.heartbeat_problem(p, 1000)
    health.write_heartbeat(p, tick, False, 1000 - 700, now=1000)
    assert "Telegram не отвечает уже 11 мин" == health.heartbeat_problem(p, 1000)
    health.write_heartbeat(p, tick, False, 1000 - 60, now=1000)
    assert health.heartbeat_problem(p, 1000) is None        # короткий сбой Telegram — не проблема
    p.write_text("{oops")
    assert "не читается" in health.heartbeat_problem(p, 1000)
    assert _t.time() > 0


def test_heartbeat_loop_writes(tmp_path, monkeypatch):
    import json

    class FakeBot:
        def __init__(self, ok):
            self.ok = ok

        async def get_me(self):
            if not self.ok:
                raise ConnectionError("нет сети")
            return object()

    p = tmp_path / "heartbeat.json"
    health.mark_tick()
    asyncio.run(health.heartbeat_loop(FakeBot(True), p, once=True))
    data = json.loads(p.read_text())
    assert data["telegram_ok"] is True and data["tick"] and data["telegram_fail_since"] is None
    asyncio.run(health.heartbeat_loop(FakeBot(False), p, once=True))
    data = json.loads(p.read_text())
    assert data["telegram_ok"] is False and data["telegram_fail_since"]


def test_healthcheck_script(tmp_path, monkeypatch, capsys):
    import healthcheck
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert healthcheck.main() == 1
    health.write_heartbeat(tmp_path / health.HEARTBEAT_FILE, datetime.now(timezone.utc), True, None)
    assert healthcheck.main() == 0
    assert "ok" in capsys.readouterr().out
