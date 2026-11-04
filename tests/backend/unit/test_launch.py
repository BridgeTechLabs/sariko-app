"""Go-live switch (docs/dev/prelaunch TC-2): app_live decides, launch_date is only shown."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import launch
from core.launch import NO_DATE, launch_status
from dao.dao_admin_config import DAOAdminConfig


@pytest.mark.parametrize("app_live, launch_date, expected", [
    (0, NO_DATE, {"prelaunch": True, "launch_date": None}),             # coming soon, date hidden
    (0, 20261101, {"prelaunch": True, "launch_date": "2026-11-01"}),    # coming soon, date shown
    (1, 20261101, {"prelaunch": False, "launch_date": "2026-11-01"}),   # live
    (0, 20200101, {"prelaunch": True, "launch_date": "2020-01-01"}),    # a past date does not go live
])
def test_launch_status(app_live, launch_date, expected):
    assert launch_status(app_live, launch_date) == expected


@pytest.mark.parametrize("settings, prelaunch", [
    ({"app_live": 1, "launch_date": 20261101}, False),
    ({"app_live": 0, "launch_date": 20261101}, True),   # 0 is a valid value, not "missing"
    ({}, True),                                         # rows missing: not live
    ({"app_live": 7, "launch_date": 20261101}, True),   # out of range: default 0
])
def test_endpoint_reads_settings(monkeypatch, settings, prelaunch):
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, k: settings.get(k))
    app = FastAPI()
    app.include_router(launch.router, prefix="/rest/v1")
    body = TestClient(app).get("/rest/v1/launch").json()
    assert body["prelaunch"] is prelaunch
    assert body["launch_date"] == ("2026-11-01" if settings else None)
