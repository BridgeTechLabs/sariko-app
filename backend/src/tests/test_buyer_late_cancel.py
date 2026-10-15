"""R4 + R6 (docs/dev/order-cancel-refund.md): the buyer may cancel a late `confirmed`
(1 h) or `delivery_failed` (30 min) order with a full refund. No DB, no network.

Run from backend/src:  python -m pytest tests/test_buyer_late_cancel.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# core.auth refuses to import without this; the value is never fetched here.
os.environ.setdefault("SUPABASE_JWKS_URL", "https://test.invalid/jwks")

import pytest
from fastapi import HTTPException

import apis.orders as orders
import apis.sellers as sellers
import dao.dao_deliveries
import dao.dao_refunds
import services.lalamove_service
from schemas import Schema
from services.lalamove_service import PlaceOrderResult, QuotationResult

refunds = []   # (order_id, reason)
cancelled_trips = []


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat()


class FakeOrders:
    """One order in memory; update_order_status honours expected_status like the real DAO."""
    row = None

    def read_order_by_id(self, order_id, user_id):
        return dict(self.row)

    def update_order_status(self, order_id, status, cancellation_reason=None, expected_status=None):
        if expected_status and self.row["status"] != expected_status:
            return None
        FakeOrders.row = {**self.row, "status": status, "cancellation_reason": cancellation_reason}
        return dict(self.row)


class FakeRefunds:
    def create_refund_for_order(self, order, reason):
        if order.get("payment_status") == "paid":
            refunds.append((order["id"], reason, order["total_amount"]))


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    refunds.clear()
    cancelled_trips.clear()
    monkeypatch.setattr(orders, "DAOOrders", FakeOrders)
    monkeypatch.setattr(dao.dao_refunds, "DAORefunds", FakeRefunds)
    monkeypatch.setattr(orders.push_service, "notify_buyer_cancelled", lambda o: None)


def order(status, **kw):
    FakeOrders.row = {"id": "o1", "status": status, "payment_status": "paid", "total_amount": 125000,
                      "delivery_appointment": None, "status_changed_at": ago(), **kw}


def buyer_cancel():
    return orders.cancel_order("o1", user={"id": "buyer"})


def assert_refused():
    with pytest.raises(HTTPException) as e:
        buyer_cancel()
    assert e.value.status_code == 400
    assert refunds == []
    return FakeOrders.row["status"]


def assert_late_cancel():
    assert buyer_cancel()["success"]
    assert FakeOrders.row["status"] == "cancelled"
    assert FakeOrders.row["cancellation_reason"] == orders.SELLER_LATE_REASON
    assert refunds == [("o1", "buyer_cancel", 125000)]  # R7.2: full total_amount


def test_r4_1_confirmed_59_min_refused():
    order("confirmed", status_changed_at=ago(minutes=59))
    assert assert_refused() == "confirmed"


def test_r4_2_confirmed_61_min_cancels_with_refund():
    order("confirmed", status_changed_at=ago(minutes=61))
    assert_late_cancel()


def test_r4_3_appointment_passed_30_min_refused():
    # confirmed days before the appointment: the clock runs from the appointment, not the confirm
    order("confirmed", status_changed_at=ago(days=2), delivery_appointment=ago(minutes=30))
    assert assert_refused() == "confirmed"


def test_r4_4_appointment_passed_61_min_cancels():
    order("confirmed", status_changed_at=ago(days=2), delivery_appointment=ago(minutes=61))
    assert_late_cancel()


def test_r4_5_ready_refused_even_when_late():
    order("ready", status_changed_at=ago(hours=3))
    assert assert_refused() == "ready"


def test_buyer_loses_race_gets_409_and_no_refund(monkeypatch):
    # Seller tapped Ready between the buyer's read and write
    order("confirmed", status_changed_at=ago(minutes=61))
    real = FakeOrders.read_order_by_id

    def read_then_seller_acts(self, order_id, user_id):
        snapshot = real(self, order_id, user_id)
        FakeOrders.row = {**FakeOrders.row, "status": "ready"}
        return snapshot
    monkeypatch.setattr(FakeOrders, "read_order_by_id", read_then_seller_acts)
    with pytest.raises(HTTPException) as e:
        buyer_cancel()
    assert e.value.status_code == 409
    assert FakeOrders.row["status"] == "ready"
    assert refunds == []


class FakeLalamove:
    def get_quotation(self, **kw):
        return QuotationResult(quotation_id="q", stop_id_0="s0", stop_id_1="s1",
                               total_fee=25000, currency="VND", distance_km=3)

    def place_order(self, **kw):
        # The buyer's late cancel lands while the seller's booking is in flight
        FakeOrders.row = {**FakeOrders.row, "status": "cancelled"}
        return PlaceOrderResult(lalamove_order_id="trip-1", status="ASSIGNING_DRIVER", share_link="")

    def cancel_order(self, lalamove_order_id):
        cancelled_trips.append(lalamove_order_id)
        return True


class FakeSellerOrders(FakeOrders):
    def read_order_by_id_for_seller(self, order_id, seller_id):
        return dict(self.row)

    def read_order_with_seller_coords(self, order_id):
        return {**self.row, "delivery_address": "D7", "delivery_lat": 10.73, "delivery_lon": 106.72,
                "seller_profiles": {"address": "Q1", "lat": 10.77, "lon": 106.70, "phone": "0901234567"},
                "users": {"name": "Buyer", "phone": "0907654321"}}


class FakeDeliveries:
    def create_delivery(self, **kw):
        return {"id": "d1", **kw}


def test_r4_6_seller_ready_vs_buyer_cancel_leaves_no_trip(monkeypatch):
    order("confirmed", status_changed_at=ago(minutes=61), delivery_method="delivery")
    monkeypatch.setattr(sellers, "DAOOrders", FakeSellerOrders)
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "seller")
    monkeypatch.setattr(services.lalamove_service, "get_lalamove_service", lambda: FakeLalamove())
    monkeypatch.setattr(dao.dao_deliveries, "DAODeliveries", FakeDeliveries)
    with pytest.raises(HTTPException) as e:
        sellers.update_seller_order_status("o1", Schema.RequestUpdateOrderStatus(status="ready"), user={"id": "s"})
    assert e.value.status_code == 409
    assert FakeOrders.row["status"] == "cancelled"
    assert cancelled_trips == ["trip-1"]


def test_r6_1_delivery_failed_29_min_refused():
    order("delivery_failed", status_changed_at=ago(minutes=29))
    assert assert_refused() == "delivery_failed"


def test_r6_2_delivery_failed_31_min_cancels_with_refund():
    order("delivery_failed", status_changed_at=ago(minutes=31))
    assert_late_cancel()


def test_r6_4_rebooked_order_has_no_cancel_deadline():
    # Rebook moves the order back to ready (and resets status_changed_at in the DB trigger)
    assert orders.cancel_after({"status": "ready", "status_changed_at": ago(hours=2)}) is None


def test_pending_cancel_unchanged():
    order("pending")
    assert buyer_cancel()["success"]
    assert FakeOrders.row["cancellation_reason"] is None
    assert refunds == [("o1", "buyer_cancel", 125000)]
