"""P0-6: a seller can't mark a ready delivery order done while its Lalamove trip still runs
(the COMPLETED webhook closes it); pickup orders and ended trips still can."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token


@pytest.fixture
def mark_done(monkeypatch):
    """PATCH status=done on a 'ready' order; returns (response, statuses written)."""
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "seller-user-1"}
    client = TestClient(app)
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")

    def call(delivery_method, delivery_status):
        written = []
        order = {"id": "order-1", "status": "ready", "payment_status": "paid", "delivery_method": delivery_method}

        class FakeOrders:
            def read_order_by_id_for_seller(self, order_id, seller_id):
                return order

            def update_order_status(self, order_id, status, reason=None, expected_status=None):
                written.append(status)
                return {**order, "status": status}

        delivery = {"status": delivery_status} if delivery_status else None
        monkeypatch.setattr("apis.sellers.DAOOrders", FakeOrders)
        monkeypatch.setattr("dao.dao_deliveries.DAODeliveries",
                            lambda: type("D", (), {"read_delivery_by_order_id": lambda self, i: delivery})())
        res = client.patch("/sellers/me/orders/order-1/status", json={"status": "done"})
        return res, written
    return call


@pytest.mark.parametrize("trip", ["ASSIGNING_DRIVER", "ON_GOING", "PICKED_UP"])
def test_done_blocked_while_trip_runs(mark_done, trip):
    res, written = mark_done("delivery", trip)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "delivery_in_progress"
    assert written == []


def test_done_allowed_for_pickup(mark_done):
    res, written = mark_done("pickup", None)
    assert res.status_code == 200
    assert written == ["done"]


def test_done_allowed_once_trip_completed(mark_done):
    res, written = mark_done("delivery", "COMPLETED")
    assert res.status_code == 200
    assert written == ["done"]


def test_seller_done_creates_no_invoice(mark_done, monkeypatch):
    """Only a delivered order is invoiced: the Lalamove COMPLETED webhook does it, never a seller's done."""
    invoiced = []
    monkeypatch.setattr("services.invoice_service.create_invoice", invoiced.append)
    res, _ = mark_done("delivery", "COMPLETED")
    assert res.status_code == 200
    assert invoiced == []


@pytest.mark.parametrize("move", [("pending", "confirmed"), ("confirmed", "ready"), ("ready", "done")])
def test_unpaid_order_never_moves_forward(monkeypatch, move):
    """02/11 PROD: an unpaid order reached done; marked ready it would book a real Lalamove trip."""
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "seller-user-1"}
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")
    written, lalamove = [], []
    order = {"id": "order-1", "status": move[0], "payment_status": "pending", "delivery_method": "delivery"}

    class FakeOrders:
        def read_order_by_id_for_seller(self, order_id, seller_id):
            return order

        def update_order_status(self, order_id, status, reason=None, expected_status=None):
            written.append(status)

    monkeypatch.setattr("apis.sellers.DAOOrders", FakeOrders)
    monkeypatch.setattr("services.lalamove_service.get_lalamove_service", lambda: lalamove.append("lalamove"))
    res = TestClient(app).patch("/sellers/me/orders/order-1/status", json={"status": move[1]})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "order_not_paid"
    assert written == [] and lalamove == []
