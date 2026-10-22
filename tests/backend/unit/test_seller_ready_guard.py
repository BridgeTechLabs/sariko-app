"""P1-4: a delivery order can't go ready while the store has no pickup point or phone
(Lalamove needs both), and the seller's order detail carries its status history."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token

FULL = {"id": "seller-1", "address": "30 Ton That Thiep", "lat": 10.77, "lon": 106.70, "phone": "0901234567"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    return TestClient(app)


@pytest.fixture
def mark_ready(client, monkeypatch):
    """PATCH status=ready on a confirmed delivery order; returns (response, statuses written, Lalamove calls)."""
    def call(profile):
        written, lalamove = [], []
        order = {"id": "order-1", "status": "confirmed", "delivery_method": "delivery"}
        monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")
        monkeypatch.setattr("services.lalamove_service.get_lalamove_service", lambda: lalamove.append("lalamove"))

        class FakeOrders:
            def read_order_by_id_for_seller(self, order_id, seller_id):
                return order

            def read_order_with_seller_coords(self, order_id):
                # No dropoff address: once past the guard the old check answers 400, before any quote.
                return {**order, "delivery_address": "", "seller_profiles": profile, "users": {}}

            def update_order_status(self, *args, **kwargs):
                written.append(args[1])

        monkeypatch.setattr("apis.sellers.DAOOrders", FakeOrders)
        res = client.patch("/sellers/me/orders/order-1/status", json={"status": "ready"})
        return res, written, lalamove
    return call


@pytest.mark.parametrize("gap, missing", [
    ({"lat": None}, ["address"]),
    ({"lon": None}, ["address"]),
    ({"address": ""}, ["address"]),
    ({"phone": None}, ["phone"]),
    ({"address": None, "phone": ""}, ["address", "phone"]),
])
def test_ready_blocked_when_store_incomplete(mark_ready, gap, missing):  # TC-15, TC-16
    res, written, lalamove = mark_ready({**FULL, **gap})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "seller_profile_incomplete"
    assert res.json()["detail"]["missing"] == missing
    assert written == [] and lalamove == []


def test_ready_passes_guard_when_complete(mark_ready):  # TC-16
    res, written, lalamove = mark_ready(FULL)
    assert res.status_code == 400         # past the guard, stopped by the existing dropoff check
    assert "Missing pickup or dropoff" in res.json()["detail"]
    assert written == [] and lalamove == []


def test_detail_has_status_history(client, monkeypatch):  # TC-17
    monkeypatch.setattr("apis.sellers._get_seller", lambda user: {"id": "seller-1"})
    monkeypatch.setattr("apis.sellers._with_deadlines", lambda orders, seller: orders)
    monkeypatch.setattr("apis.sellers.complaints_for_order", lambda order, user_id, role: {})   # complaints: own tests
    history = {"order-1": [{"status": "pending", "changed_at": "2026-10-20T03:00:00+00:00"},
                           {"status": "confirmed", "changed_at": "2026-10-20T03:05:00+00:00"}],
               "order-2": []}

    class FakeOrders:
        def read_order_by_id_for_seller(self, order_id, seller_id):
            return {"id": order_id, "status": "confirmed"}

        def read_status_history(self, order_id):
            return history[order_id]

    monkeypatch.setattr("apis.sellers.DAOOrders", FakeOrders)
    assert client.get("/sellers/me/orders/order-1").json()["order"]["status_history"] == history["order-1"]
    assert client.get("/sellers/me/orders/order-2").json()["order"]["status_history"] == []


def test_status_history_query():  # TC-17: only this order, oldest first
    from dao.dao_orders import DAOOrders
    calls = []

    class Q:
        def __getattr__(self, name):
            def record(*args, **kwargs):
                calls.append((name, args, kwargs))
                return self
            return record

        def execute(self):
            return type("R", (), {"data": []})()

    dao = DAOOrders.__new__(DAOOrders)
    dao._supabase_client = type("C", (), {"table": lambda self, t: calls.append(("table", (t,), {})) or Q()})()
    assert dao.read_status_history("order-1") == []
    assert ("table", ("history_order_status",), {}) in calls
    assert ("eq", ("order_id", "order-1"), {}) in calls
    assert ("order", ("changed_at",), {}) in calls
