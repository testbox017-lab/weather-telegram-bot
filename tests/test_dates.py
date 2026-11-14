from datetime import date

from dates import (build_cal_cb, build_date_cb, calendar_days, date_source, parse_cal_cb, parse_date,
                   parse_date_cb, source_error, split_date_args, TOO_FAR)

TODAY = date(2026, 11, 14)


def test_parse_date_formats():
    assert parse_date("21.11", TODAY) == date(2026, 11, 21)
    assert parse_date("21.11.2026", TODAY) == date(2026, 11, 21)
    assert parse_date("1.2.26", TODAY) == date(2026, 2, 1)
    assert parse_date("21/11/1999", TODAY) == date(1999, 11, 21)
    assert parse_date("завтра", TODAY) == date(2026, 11, 15)
    assert parse_date("Послезавтра", TODAY) == date(2026, 11, 16)
    assert parse_date("вчера", TODAY) == date(2026, 11, 13)


def test_parse_date_invalid():
    for bad in [None, "", "31.02", "32.01", "13.13.2026", "Москва", "2026-11-21", "21.11.202"]:
        assert parse_date(bad, TODAY) is None, bad


def test_split_date_args():
    assert split_date_args("завтра Казань", TODAY) == (date(2026, 11, 15), "Казань")
    assert split_date_args("21.11 51.18, 32.83", TODAY) == (date(2026, 11, 21), "51.18, 32.83")
    assert split_date_args("", TODAY) == (None, "")
    assert split_date_args("Казань", TODAY) == (None, "")


def test_date_source():
    assert date_source(TODAY, TODAY) == "forecast"
    assert date_source(date(2026, 11, 29), TODAY) == "forecast"   # +15
    assert date_source(date(2026, 11, 30), TODAY) == "future"     # +16
    assert source_error("future") == TOO_FAR
    assert date_source(date(2026, 11, 7), TODAY) == "forecast"    # неделя назад
    assert date_source(date(2026, 11, 6), TODAY) == "archive"
    assert date_source(date(1940, 1, 1), TODAY) == "archive"
    assert date_source(date(1939, 12, 31), TODAY) == "old"
    assert source_error("forecast") is None and source_error("archive") is None


def test_date_callbacks():
    cb = build_date_cb(date(2026, 11, 21), 51.1812, 32.8349)
    assert cb == "d:20261121:51.181:32.835"
    assert parse_date_cb(cb) == (date(2026, 11, 21), 51.181, 32.835)
    assert len(build_date_cb(date(1940, 1, 1), -89.9999, -179.9999).encode()) <= 64
    for bad in [None, "d:2026112:1:1", "d:20261340:1:1", "x:20261121:1:1", "d:20261121:99:1"]:
        assert parse_date_cb(bad) is None, bad
    assert parse_cal_cb(build_cal_cb("p", 51.18, 32.83)) == ("p", 51.18, 32.83)
    assert parse_cal_cb("c:z:1:1") is None


def test_calendar_days():
    future = calendar_days("f", TODAY)
    assert len(future) == 16 and future[0] == TODAY and future[-1] == date(2026, 11, 29)
    past = calendar_days("p", TODAY)
    assert len(past) == 14 and past[-1] == date(2026, 11, 13) and past[0] == date(2026, 10, 31)
