"""P1-3: the seller's order list keeps running orders of any age but only N days of done /
cancelled ones; older orders are found by code or buyer name."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_orders import DAOOrders


class FakeQuery:
    """Records every builder call; execute() answers from `rows_for(calls)`."""

    def __init__(self, log, rows_for):
        self.calls, self._rows_for = [], rows_for
        log.append(self.calls)

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args))
            return self
        return record

    def execute(self):
        return type("R", (), {"data": self._rows_for(self.calls)})()


def fake_dao(rows_for=lambda calls: []):
    log = []
    dao = DAOOrders.__new__(DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, t: FakeQuery(log, rows_for)})()
    return dao, log


def test_list_filters(monkeypatch):  # TC-8
    dao, log = fake_dao()
    since = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)
    dao.read_orders_by_seller_id("seller-1", since)
    calls = log[0]
    assert ("eq", ("seller_id", "seller-1")) in calls
    assert ("eq", ("payment_status", "paid")) in calls
    assert ("or_", ("status.not.in.(done,cancelled),created_at.gte.2026-09-20T08:00:00",)) in calls


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    monkeypatch.setattr("apis.sellers._get_seller", lambda user: {"id": "seller-1"})
    monkeypatch.setattr("apis.sellers._with_deadlines", lambda orders, seller: orders)
    return TestClient(app)


@pytest.mark.parametrize("setting, days", [(30, 30), (7, 7), (None, 30), (0, 30), ("abc", 30)])
def test_history_days_setting(client, monkeypatch, setting, days):  # TC-8, TC-9
    seen = {}
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, key: setting)

    class Orders:
        def read_orders_by_seller_id(self, seller_id, since):
            seen["since"] = since
            return []

    monkeypatch.setattr("apis.sellers.DAOOrders", Orders)
    res = client.get("/sellers/me/orders")
    assert res.status_code == 200
    assert res.json()["history_days"] == days
    expected = datetime.now(timezone.utc) - timedelta(days=days)
    assert abs((seen["since"] - expected).total_seconds()) < 5


def _search(client, monkeypatch, q):
    seen = {}

    class Orders:
        def search_orders_for_seller(self, seller_id, code, name, limit):
            seen.update(seller_id=seller_id, code=code, name=name, limit=limit)
            return []

    monkeypatch.setattr("apis.sellers.DAOOrders", Orders)
    return client.get("/sellers/me/orders/search", params={"q": q}), seen


@pytest.mark.parametrize("q", ["#54CB066E", "54cb066e", "54CB"])
def test_search_by_code(client, monkeypatch, q):  # TC-10
    res, seen = _search(client, monkeypatch, q)
    assert res.status_code == 200
    assert seen["code"] == q.lstrip("#").lower()
    assert seen["seller_id"] == "seller-1" and seen["limit"] == 20


def test_search_too_short(client, monkeypatch):  # TC-10
    res, _ = _search(client, monkeypatch, "a")
    assert res.status_code == 422


@pytest.mark.parametrize("q, name", [("van a", "van a"), ("a,b)", "ab"), ("%_*", None), ("O'Brien-Cruz", "O'Brien-Cruz")])
def test_search_by_name_is_sanitised(client, monkeypatch, q, name):  # TC-11
    res, seen = _search(client, monkeypatch, q)
    assert res.status_code == 200
    assert seen["name"] == name
    assert seen["code"] is None


def test_search_code_range_and_merge():  # TC-10, TC-11
    by_code = {"id": "54cb066e-5bcf-4e23-a5ef-010d4affacb0", "created_at": "2026-10-01T00:00:00"}
    by_name = {"id": "aaaa0000-0000-0000-0000-000000000000", "created_at": "2026-10-05T00:00:00"}

    def rows_for(calls):
        return [by_name] if ("ilike", ("users.name", "*bea*")) in calls else [by_code]

    dao, log = fake_dao(rows_for)
    rows = dao.search_orders_for_seller("seller-1", "54cb", "bea", 20)
    assert [r["id"] for r in rows] == [by_name["id"], by_code["id"]]
    code_q, name_q = log
    assert ("gte", ("id", "54cb0000-0000-0000-0000-000000000000")) in code_q
    assert ("lte", ("id", "54cbffff-ffff-ffff-ffff-ffffffffffff")) in code_q
    for q in (code_q, name_q):
        assert ("eq", ("seller_id", "seller-1")) in q
        assert ("eq", ("payment_status", "paid")) in q
    assert any(c[0] == "select" and "users!inner(" in c[1][0] for c in name_q)


def test_buyer_gets_403(monkeypatch):  # TC-12
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    monkeypatch.setattr("apis.sellers.DAOSellerProfiles",
                        lambda: type("P", (), {"read_seller_profile_by_user_id": lambda self, uid: None})())
    res = TestClient(app).get("/sellers/me/orders/search", params={"q": "54cb066e"})
    assert res.status_code == 403
