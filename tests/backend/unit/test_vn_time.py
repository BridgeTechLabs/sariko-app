"""core/vn_time.py — dates are Vietnam (GMT+7) dates, not UTC ones."""
from datetime import datetime, timezone

import pytest

from core.vn_time import vn_today


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 11, 2, 16, 59, tzinfo=timezone.utc), "2026-11-02"),   # 23:59 in VN
    (datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc), "2026-11-03"),    # 00:00 next day in VN
    (datetime(2026, 12, 31, 17, 30, tzinfo=timezone.utc), "2027-01-01"),  # year rolls over in VN first
])
def test_vn_today(now, expected):
    assert vn_today(now) == expected
