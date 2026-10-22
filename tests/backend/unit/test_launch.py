"""Pre-launch switch (docs/dev/prelaunch TC-2): Vietnam date vs admin_settings public_launch_date."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import launch
from core.launch import NO_DATE, launch_status
from dao.dao_admin_config import DAOAdminConfig

NOON_VN_22 = datetime(2026, 10, 22, 5, 0, tzinfo=timezone.utc)      # 12:00 on 22/10 in Vietnam
LATE_UTC_22 = datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc)   # 06:30 on 23/10 in Vietnam


@pytest.mark.parametrize("launch_date, now, prelaunch, shown", [
    (20261021, NOON_VN_22, False, "2026-10-21"),   # before today: open
    (20261022, NOON_VN_22, False, "2026-10-22"),   # opening day: open
    (20261023, NOON_VN_22, True, "2026-10-23"),    # tomorrow: coming soon
    (NO_DATE, NOON_VN_22, True, None),             # no date announced
    (20261023, LATE_UTC_22, False, "2026-10-23"),  # still 22/10 in UTC, already 23/10 in Vietnam
])
def test_launch_status(launch_date, now, prelaunch, shown):
    assert launch_status(launch_date, now) == {"prelaunch": prelaunch, "launch_date": shown}


def test_endpoint_reads_setting(monkeypatch):
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_positive_int", lambda self, k, d: {"public_launch_date": 99991231}.get(k, d))
    app = FastAPI()
    app.include_router(launch.router, prefix="/rest/v1")
    assert TestClient(app).get("/rest/v1/launch").json() == {"success": True, "prelaunch": True, "launch_date": None}
