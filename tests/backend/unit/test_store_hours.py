"""Open now = manual switch AND inside the weekly hours (VN time); no weekly hours = all day."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from core.store_hours import is_open_now
from schemas import Schema


def at(hhmm, day=12):  # a VN wall-clock time on 2026-10-<day> (12 = Monday ... 18 = Sunday), given as UTC
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, tzinfo=timezone.utc) + timedelta(hours=h - 7, minutes=m)


def week(**days):  # week(mon=("10:00", "20:00"), fri=None) -> weekly_hours; days not given = day off
    keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return {str(i + 1): (dict(zip(("open", "close"), days[k])) if days.get(k) else None) for i, k in enumerate(keys)}


MON_10_20 = week(mon=("10:00", "20:00"))
FRI_NIGHT = week(fri=("18:00", "02:00"), sat=("10:00", "12:00"))


@pytest.mark.parametrize("is_open, hours, now, expected", [
    (False, None, at("12:00"), False),                     # switch off wins
    (False, MON_10_20, at("12:00"), False),
    (True, None, at("03:00"), True),                       # no weekly hours = all day
    (None, None, at("03:00"), True),                       # NULL switch = open (column default)
    (True, MON_10_20, at("09:59"), False),
    (True, MON_10_20, at("10:00"), True),
    (True, MON_10_20, at("20:00"), False),                 # closing time is exclusive
    (True, MON_10_20, at("12:00", 13), False),             # Tuesday is a day off
    (True, FRI_NIGHT, at("23:30", 16), True),              # Friday night
    (True, FRI_NIGHT, at("01:00", 17), True),              # 01:00 Saturday still on Friday's hours
    (True, FRI_NIGHT, at("03:00", 17), False),             # after Friday's slot, before Saturday's
    (True, FRI_NIGHT, at("10:30", 17), True),              # Saturday's own slot
    (True, FRI_NIGHT, at("01:00", 16), False),             # Thursday was off: nothing carries into Friday
    (True, week(mon=("08:00", "08:00")), at("03:00"), True),       # same time = the whole day
    (True, week(mon=("08:00", "08:00")), at("03:00", 13), False),  # ... only that day
])
def test_is_open_now(is_open, hours, now, expected):
    assert is_open_now(is_open, hours, now=now) is expected


def test_malformed_day_counts_as_day_off(caplog):
    # weekly_hours has no DB check: a broken row must not 500 the home page list or the cart
    bad = week(mon=("10:00", "20:00"), tue=("10:00", "20:00"))
    bad["1"] = {"open": "10:00"}                 # no closing time
    bad["2"] = {"open": "25:00", "close": "20:00"}
    assert is_open_now(True, bad, now=at("12:00"), seller_id="s1") is False
    assert is_open_now(True, bad, now=at("12:00", 13)) is False
    assert is_open_now(True, "garbage", now=at("12:00")) is False
    fine_today = {**bad, "3": {"open": "10:00", "close": "20:00"}}
    assert is_open_now(True, fine_today, now=at("12:00", 14)) is True   # Wednesday ok, Tuesday's break only logged
    assert "seller=s1" in caplog.text and "day off" in caplog.text


def test_weekly_hours_request():
    full = week(mon=("10:00", "20:00"), fri=("18:00", "02:00"))
    assert Schema.RequestSetStoreHours(weekly_hours=full).as_json() == full
    assert Schema.RequestSetStoreHours(weekly_hours=None).as_json() is None   # all day
    with_seconds = Schema.RequestSetStoreHours(weekly_hours={**full, "1": {"open": "10:00:00", "close": "20:00"}})
    assert with_seconds.as_json()["1"] == {"open": "10:00", "close": "20:00"}
    for bad in ({k: v for k, v in full.items() if k != "7"},               # a day missing
                {**full, "1": {"open": "25:00", "close": "20:00"}},        # not a time
                {**full, "1": {"open": "10:00"}}):                         # no closing time
        with pytest.raises(ValidationError):
            Schema.RequestSetStoreHours(weekly_hours=bad)
    with pytest.raises(ValidationError):
        Schema.RequestSetStoreHours()   # must say null explicitly to mean all day
