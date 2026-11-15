"""Сторож сервера deploy/watchdog.sh: запускается с поддельными docker и curl во временной папке."""
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "deploy" / "watchdog.sh"
pytestmark = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash") or not shutil.which("python3"),
                                reason="нужен bash (сервер — Linux)")

FAKE_DOCKER = """#!/bin/bash
case "$1" in
  inspect) [ -f "$W/missing" ] && exit 1; cat "$W/inspect" ;;
  logs) cat "$W/logs" 2>/dev/null ;;
esac
"""
FAKE_CURL = """#!/bin/bash
url="" text=""
while [ $# -gt 0 ]; do
  case "$1" in
    --data-urlencode) shift; case "$1" in text=*) text=${1#text=} ;; silent=*) ;; esac ;;
    http*) url=$1 ;;
  esac
  shift
done
case "$url" in
  *api.telegram.org*) [ -f "$W/tg_fail" ] && exit 22; printf '%s\\n---\\n' "$text" >> "$W/sent"; exit 0 ;;
  *) [ -f "$W/om_fail" ] && exit 7; exit 0 ;;
esac
"""


class Box:
    def __init__(self, tmp: Path):
        self.w = tmp
        app = tmp / "app"
        (app / "data").mkdir(parents=True)
        (app / ".env").write_text('BOT_TOKEN="123:abc"\n', encoding="utf-8")
        (app / "data" / "saved_places.json").write_text('{"4242": []}', encoding="utf-8")
        (app / "data" / "prefs.json").write_text('{"4242": {}}', encoding="utf-8")
        self.backups = tmp / "backups"
        self.backups.mkdir()
        self.backup(hours_ago=3)
        for name, body in (("docker", FAKE_DOCKER), ("curl", FAKE_CURL)):
            p = tmp / name
            p.write_text(body)
            p.chmod(0o755)
        (tmp / "boot_id").write_text("boot-1\n")
        self.container("running", 0)
        self.now = int(time.time())

    def backup(self, hours_ago: float):
        f = self.backups / "weather-bot-2026-11-15_0330.tar.gz"
        f.write_bytes(b"x")
        t = time.time() - hours_ago * 3600
        os.utime(f, (t, t))

    def container(self, status: str, restarts: int, started: str = "2026-11-15T07:00:00Z"):
        (self.w / "inspect").write_text(f"{status} {restarts} {started}\n")

    def flag(self, name: str, on: bool = True):
        p = self.w / name
        p.write_text("1") if on else p.unlink(missing_ok=True)

    def run(self, *args, minutes: int = 5, **env):
        self.now += minutes * 60
        (self.w / "sent").unlink(missing_ok=True)
        e = {**os.environ, "W": str(self.w), "APP": str(self.w / "app"), "STATE": str(self.w / "state"),
             "BACKUPS": str(self.backups), "DOCKER": str(self.w / "docker"), "CURL": str(self.w / "curl"),
             "BOOT_ID_FILE": str(self.w / "boot_id"), "DEPLOY_LOCK": str(self.w / "deploy.lock"),
             "DISK_LIMIT": "100", "NOW": str(self.now), **env}
        r = subprocess.run(["bash", str(SCRIPT), *args], env=e, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        sent = self.w / "sent"
        return [m.strip() for m in sent.read_text().split("---") if m.strip()] if sent.exists() else []


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


def test_all_good_is_silent(box):
    assert box.run() == []
    assert box.run() == []


def test_test_message(box):
    sent = box.run("--test")
    assert len(sent) == 1 and "Сторож сервера работает" in sent[0]


def test_container_down_then_recovered(box):
    box.run()
    box.container("exited", 0)
    sent = box.run()
    assert len(sent) == 1 and "контейнер не работает (состояние: exited)" in sent[0]
    assert box.run() == []  # не повторяет каждые 5 минут
    box.container("running", 0)
    sent = box.run()
    assert len(sent) == 1 and sent[0].startswith("🟢 Снова в порядке: контейнер не работает")


def test_reminder_after_12h(box):
    box.container("restarting", 3)
    assert len(box.run()) == 1
    sent = box.run(minutes=12 * 60)
    assert len(sent) == 1 and sent[0].startswith("🔴 Всё ещё")


def test_crash_restart_reported_once(box):
    box.run()
    box.container("running", 1)
    sent = box.run()
    assert len(sent) == 1 and "упал и перезапустился" in sent[0]
    assert box.run() == []
    box.container("running", 0, started="2026-11-15T09:00:00Z")  # деплой: новый контейнер, счётчик с нуля
    assert box.run() == []


def test_log_errors_rate_limited(box):
    box.run()
    (box.w / "logs").write_text("INFO ok\nERROR:root:weather error\nTraceback (most recent call last):\n"
                                "ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramNetworkError\n")
    sent = box.run()
    assert len(sent) == 1 and "ошибки: 2" in sent[0] and "weather error" in sent[0]
    assert "Failed to fetch" not in sent[0]
    assert box.run() == []  # следующие ошибки копятся до истечения часа
    sent = box.run(minutes=60)
    assert len(sent) == 1 and "ошибки: 4" in sent[0]


def test_old_backup_and_full_disk(box):
    box.backup(hours_ago=30)
    sent = box.run(DISK_LIMIT="0")
    assert any("бэкап сделан 30 ч назад" in s for s in sent)
    assert any("диск заполнен" in s for s in sent)
    box.backup(hours_ago=1)
    sent = box.run()
    assert len(sent) == 2 and all(s.startswith("🟢") for s in sent)


def test_open_meteo_after_three_failures(box):
    box.flag("om_fail")
    assert box.run() == [] and box.run() == []
    sent = box.run()
    assert len(sent) == 1 and "Open-Meteo не отвечает уже 3" in sent[0]
    box.flag("om_fail", False)
    assert box.run()[0].startswith("🟢")


def test_reboot_detected(box):
    box.run()
    (box.w / "boot_id").write_text("boot-2\n")
    sent = box.run()
    assert len(sent) == 1 and "перезагружался" in sent[0]
    assert box.run() == []


def test_telegram_down_retries_next_time(box):
    box.container("exited", 0)
    box.flag("tg_fail")
    assert box.run() == []
    box.flag("tg_fail", False)
    assert len(box.run()) == 1  # тревога не потерялась


def test_deploy_in_progress_skips_container(box):
    import fcntl

    box.container("exited", 0)
    with open(box.w / "deploy.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert box.run() == []
    assert len(box.run()) == 1


def test_no_chat_found_sends_nothing(box):
    (box.w / "app" / "data" / "prefs.json").write_text('{"1": {}}')  # двое пользователей — неясно, кому
    box.container("exited", 0)
    assert box.run() == []
    (box.w / "app" / ".env").write_text("BOT_TOKEN=123:abc\nADMIN_CHAT_ID=4242\n")
    assert len(box.run()) == 1
