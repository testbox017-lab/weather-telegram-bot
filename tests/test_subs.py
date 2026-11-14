import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from subs import (SUB_LIMIT, Subscriptions, describe, next_run, parse_schedule, run_due,
                  split_place_schedule)
from weather import Place

UTC = timezone.utc
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
P = Place("Бахмач", 51.18, 32.83)


def test_parse_intervals():
    assert parse_schedule("3") == {"hours": 3}
    assert parse_schedule("3ч") == {"hours": 3}
    assert parse_schedule("каждые 6 ч") == {"hours": 6}
    assert parse_schedule("1 час") == {"hours": 1}
    assert parse_schedule("24") == {"hours": 24}


def test_parse_times():
    assert parse_schedule("08:00") == {"times": ["08:00"]}
    assert parse_schedule("в 7.30") == {"times": ["07:30"]}
    assert parse_schedule("20:00, 07:30") == {"times": ["07:30", "20:00"]}
    assert parse_schedule("7:00 и 19:00") == {"times": ["07:00", "19:00"]}


def test_parse_invalid():
    for bad in [None, "", "5", "2ч", "25:00", "12:60", "Москва", "08:00 Казань",
                "06:00, 09:00, 12:00, 18:00", "51.18"]:
        assert parse_schedule(bad) is None, bad


def test_split_place_schedule():
    assert split_place_schedule("Бахмач 3ч") == ("Бахмач", {"hours": 3})
    assert split_place_schedule("Нижний Новгород 08:00, 20:00") == ("Нижний Новгород",
                                                                     {"times": ["08:00", "20:00"]})
    assert split_place_schedule("08:00") == ("", {"times": ["08:00"]})
    assert split_place_schedule("Бахмач") == ("Бахмач", None)
    assert split_place_schedule("") == ("", None)


def test_describe():
    assert describe({"hours": 1}) == "каждый час"
    assert describe({"hours": 3}) == "каждые 3 ч"
    assert describe({"hours": 24}) == "раз в сутки"
    assert describe({"times": ["08:00", "20:00"]}) == "ежедневно в 08:00, 20:00"


def test_next_run_interval():
    assert next_run({"hours": 3}, NOW) == NOW + timedelta(hours=3)


def test_next_run_daily_timezone():
    # Киев зимой UTC+2: 12:00 UTC = 14:00 местного → 08:00 уже прошло, следующее завтра 06:00 UTC
    assert next_run({"times": ["08:00"]}, NOW, "Europe/Kyiv") == datetime(2026, 11, 15, 6, 0, tzinfo=UTC)
    # 20:00 местного — сегодня в 18:00 UTC; из двух времён берётся ближайшее
    assert next_run({"times": ["08:00", "20:00"]}, NOW, "Europe/Kyiv") == datetime(2026, 11, 14, 18, 0, tzinfo=UTC)
    assert next_run({"times": ["13:00"]}, NOW, "Asia/Tokyo") == datetime(2026, 11, 15, 4, 0, tzinfo=UTC)


def test_next_run_dst_safe():
    # в ночь на 29.03.2026 Европа/Киев переходит на летнее время (UTC+3)
    before = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)
    assert next_run({"times": ["08:00"]}, before, "Europe/Kyiv") == datetime(2026, 3, 29, 5, 0, tzinfo=UTC)


def test_storage_due_advance_and_persist(tmp_path):
    path = tmp_path / "subscriptions.json"
    s = Subscriptions(path)
    sub = s.add(1, P, {"hours": 3}, "Europe/Kyiv", NOW)
    assert sub["id"] == 1 and s.due(NOW) == []
    later = NOW + timedelta(hours=3)
    assert [uid for uid, _ in s.due(later)] == [1]
    s.advance(1, 1, later)
    assert s.due(later) == []
    again = Subscriptions(path)  # пережило перезапуск
    assert again.list(1)[0]["next"] == (later + timedelta(hours=3)).isoformat()


def test_missed_run_sent_once(tmp_path):
    s = Subscriptions(tmp_path / "s.json")
    s.add(1, P, {"hours": 1}, "UTC", NOW)
    down_until = NOW + timedelta(hours=10)  # бот был выключен 10 часов
    sent = []

    async def send(uid, sub):
        sent.append(uid)

    assert asyncio.run(run_due(s, down_until, send, pause=0)) == 1
    assert asyncio.run(run_due(s, down_until, send, pause=0)) == 0
    assert sent == [1]
    assert s.list(1)[0]["next"] == (down_until + timedelta(hours=1)).isoformat()


def test_limit_and_replace(tmp_path):
    s = Subscriptions(tmp_path / "s.json")
    for h in (1, 3, 6, 12, 24):
        assert s.add(1, P, {"hours": h}, "UTC", NOW)
    assert s.add(1, Place("Киев", 50.45, 30.52), {"hours": 3}, "UTC", NOW) is None  # лимит
    assert s.add(1, P, {"hours": 3}, "UTC", NOW) is not None  # та же точка и расписание — замена
    assert len(s.list(1)) == SUB_LIMIT
    assert s.remove_index(1, 1)["sched"] == {"hours": 1}
    assert s.remove_index(1, 9) is None
    assert s.remove_all(1) == SUB_LIMIT - 1 and s.list(1) == []


class Blocked(Exception):
    pass


def test_blocked_user_cleanup_and_errors(tmp_path):
    s = Subscriptions(tmp_path / "s.json")
    s.add(1, P, {"hours": 1}, "UTC", NOW)
    s.add(1, P, {"hours": 3}, "UTC", NOW)
    s.add(2, P, {"hours": 1}, "UTC", NOW)
    s.add(3, P, {"hours": 1}, "UTC", NOW)

    async def send(uid, sub):
        if uid == 1:
            raise Blocked()
        if uid == 3:
            raise RuntimeError("сеть")

    later = NOW + timedelta(hours=1)
    assert asyncio.run(run_due(s, later, send, (Blocked,), pause=0)) == 1
    assert s.list(1) == []                 # заблокировал бота — рассылки удалены
    assert len(s.list(3)) == 1             # временная ошибка — рассылка остаётся
    assert s.due(later) == []              # и переносится на следующий раз


def test_callback_data_fits():
    for cb in [f"sh:12:{-89.9999:.3f}:{-179.9999:.3f}", f"st:2030:{-89.9999:.3f}:{-179.9999:.3f}",
               f"sb:{-89.9999:.3f}:{-179.9999:.3f}", "su:rm:99999"]:
        assert len(cb.encode()) <= 64


def test_split_short():
    from subs import split_short
    assert split_short("Бахмач 3ч кратко") == ("Бахмач 3ч", True)
    assert split_short("Кратко Бахмач") == ("Бахмач", True)
    assert split_short("Бахмач 08:00") == ("Бахмач 08:00", False)
    assert split_short(None) == ("", False)


def test_short_flag_and_toggle(tmp_path):
    s = Subscriptions(tmp_path / "s.json")
    sub = s.add(1, P, {"hours": 3}, "Europe/Kyiv", NOW, short=True)
    assert sub["short"] is True
    assert s.toggle_short(1, sub["id"])["short"] is False
    assert Subscriptions(tmp_path / "s.json").list(1)[0]["short"] is False  # сохранилось в файл
    assert s.toggle_short(1, 99) is None
