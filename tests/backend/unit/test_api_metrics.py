"""T135 API response times (docs/dev/monitoring Q1, TC-1..TC-4). No DB: the DAOs are faked."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from dao.dao_admin_config import DAOAdminConfig
from services import api_metrics


@pytest.fixture(autouse=True)
def fresh():
    api_metrics.take()   # start every test with an empty bucket
    yield
    api_metrics.take()


@pytest.fixture
def client():
    app = FastAPI()
    app.middleware("http")(api_metrics.middleware)

    @app.get("/rest/v1/orders/{order_id}")
    def order(order_id: str):
        if order_id == "missing":
            raise HTTPException(status_code=404)
        return {"id": order_id}

    @app.get("/health")
    def health():
        return {"ok": True}

    return TestClient(app)


def test_tc1_route_pattern_counted_health_skipped(client):  # TC-1
    for oid in ("a1", "b2", "c3"):
        assert client.get(f"/rest/v1/orders/{oid}?secret=x").status_code == 200
    assert client.get("/health").status_code == 200
    client.get("/rest/v1/orders/missing")
    client.get("/no/such/path/123")
    rows = {(r["method"], r["route"], r["status_class"]): r for r in api_metrics.take()}
    assert rows[("GET", "/rest/v1/orders/{order_id}", "2xx")]["count"] == 3
    assert rows[("GET", "/rest/v1/orders/{order_id}", "4xx")]["count"] == 1
    assert ("GET", "(unmatched)", "4xx") in rows                  # a random path never becomes its own route
    assert not any("health" in k[1] or "a1" in k[1] or "secret" in k[1] for k in rows)


def test_tc2_one_row_with_percentiles(monkeypatch):  # TC-2
    since = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
    api_metrics.take(since)                                       # the bucket starts at `since`
    for ms in range(10, 101, 10):
        api_metrics.record("GET", "/rest/v1/sellers/{slug}", 200, ms)
    written = []
    monkeypatch.setattr(api_metrics, "DAOApiMetrics", lambda: type("D", (), {"insert_many": lambda self, rows: written.extend(rows)})())
    assert api_metrics.flush(since + timedelta(minutes=5)) == 1
    (row,) = written
    assert row == {"bucket_start": since.isoformat(), "method": "GET", "route": "/rest/v1/sellers/{slug}", "status_class": "2xx",
                   "count": 10, "p50_ms": 50, "p95_ms": 100, "max_ms": 100}
    assert api_metrics.take() == []                               # counting restarted


def test_tc3_write_error_drops_the_batch(monkeypatch, client, caplog):  # TC-3
    def boom(self, rows):
        raise Exception("db down")
    monkeypatch.setattr(api_metrics, "DAOApiMetrics", lambda: type("D", (), {"insert_many": boom})())
    assert client.get("/rest/v1/orders/a1").status_code == 200   # requests never wait on the DB
    assert api_metrics.flush() == 0
    assert "1 rows not written, dropped" in caplog.text
    assert api_metrics.take() == []                               # the counters start again from 0
    assert client.get("/rest/v1/orders/a1").status_code == 200
    assert api_metrics.take()[0]["count"] == 1


def test_flush_nothing_counted(monkeypatch):
    monkeypatch.setattr(api_metrics, "DAOApiMetrics", lambda: pytest.fail("no write when nothing was counted"))
    assert api_metrics.flush() == 0


@pytest.mark.parametrize("setting, days", [(30, 30), (7, 7), (None, 30), (0, 30)])
def test_tc4_cleanup_cutoff(monkeypatch, setting, days):  # TC-4: rows older than the retention are deleted
    asked = []
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, key: setting)
    monkeypatch.setattr(api_metrics, "DAOApiMetrics", lambda: type("D", (), {"delete_before": lambda self, c: asked.append(c)})())
    now = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
    cutoff = api_metrics.cleanup(now)
    assert asked == [cutoff] and cutoff == (now - timedelta(days=days)).isoformat()
    # a row 31 days old is before the 30-day cut-off, a row 1 day old is kept
    if days == 30:
        assert (now - timedelta(days=31)).isoformat() < cutoff < (now - timedelta(days=1)).isoformat()


def test_dao_queries():  # the DAO writes / deletes on metrics_api only
    from dao.dao_api_metrics import DAOApiMetrics
    calls = []

    class Q:
        def __getattr__(self, name):
            def record(*args, **kwargs):
                calls.append((name, args))
                return self
            return record

    dao = DAOApiMetrics.__new__(DAOApiMetrics)
    dao._table_name = "metrics_api"
    dao._supabase_client = type("C", (), {"table": lambda self, t: (calls.append(("table", (t,))), Q())[1]})()
    dao.delete_before("2026-09-27T03:00:00+00:00")
    assert ("table", ("metrics_api",)) in calls and ("lt", ("bucket_start", "2026-09-27T03:00:00+00:00")) in calls
