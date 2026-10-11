"""Open now = manual switch AND inside the daily hours (VN time); no hours = all day."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.store_hours import is_open_now
from schemas import Schema


def at(hhmm):  # a VN wall-clock time, given as UTC (VN = UTC+7)
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, 12, (h - 7) % 24, m, tzinfo=timezone.utc)


@pytest.mark.parametrize("is_open, opens, closes, now, expected", [
    (False, None, None, "12:00", False),                 # switch off wins
    (False, "10:00:00", "20:00:00", "12:00", False),
    (True, None, None, "03:00", True),                   # no hours = all day
    (None, None, None, "03:00", True),                   # NULL switch = open (column default)
    (True, "10:00:00", "20:00:00", "09:59", False),
    (True, "10:00:00", "20:00:00", "10:00", True),
    (True, "10:00:00", "20:00:00", "20:00", False),      # closing time is exclusive
    (True, "18:00:00", "02:00:00", "23:30", True),       # overnight
    (True, "18:00:00", "02:00:00", "01:59", True),
    (True, "18:00:00", "02:00:00", "12:00", False),
    (True, "08:00:00", "08:00:00", "03:00", True),       # same time = 24h
])
def test_is_open_now(is_open, opens, closes, now, expected):
    assert is_open_now(is_open, opens, closes, now=at(now)) is expected


def test_hours_must_come_in_pairs():
    Schema.RequestSetStoreHours(opening_time="10:00", closing_time="20:00")
    Schema.RequestSetStoreHours()  # clear both = all day
    with pytest.raises(ValidationError):
        Schema.RequestSetStoreHours(opening_time="10:00")
