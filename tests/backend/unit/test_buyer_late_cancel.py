"""R4 + R6 (docs/dev/order-cancel-refund.md): the buyer may cancel a late `confirmed`
(1 h) or `delivery_failed` (30 min) order with a full refund. No DB, no network.

Run from tests/backend:  pytest unit/test_buyer_late_cancel.py
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import apis.deliveries as deliveries
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


class FakeSettings:
    """admin_settings rows; empty = every window falls back to its default."""
    rows = {}

    def get_positive_int(self, key, default):
        return self.rows.get(key, default)

    def get_minutes(self, key, default):
        return timedelta(minutes=self.get_positive_int(key, default))


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    refunds.clear()
    cancelled_trips.clear()
    FakeSettings.rows = {}
    monkeypatch.setattr(orders, "DAOAdminConfig", FakeSettings)
    monkeypatch.setattr(sellers, "DAOAdminConfig", FakeSettings)
    monkeypatch.setattr(deliveries, "DAOAdminConfig", FakeSettings)
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


class NoDriverLalamove(FakeLalamove):
    tries = 0

    def place_order(self, **kw):
        NoDriverLalamove.tries += 1
        raise RuntimeError("no driver")


def test_booking_attempts_come_from_admin_settings(monkeypatch):
    FakeSettings.rows = {"driver_booking_attempts": 2}
    NoDriverLalamove.tries = 0
    order("confirmed", delivery_method="delivery")
    monkeypatch.setattr(sellers, "DAOOrders", FakeSellerOrders)
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "seller")
    monkeypatch.setattr(services.lalamove_service, "get_lalamove_service", lambda: NoDriverLalamove())
    with pytest.raises(HTTPException) as e:
        sellers.update_seller_order_status("o1", Schema.RequestUpdateOrderStatus(status="ready"), user={"id": "s"})
    assert e.value.status_code == 503
    assert NoDriverLalamove.tries == 2
    assert FakeOrders.row["status"] == "cancelled"
    assert FakeOrders.row["cancellation_reason"] == "Driver booking failed"  # OrderStatusHeader.vue translates it
    assert refunds == [("o1", "driver_booking_failed", 125000)]


def test_rebook_max_comes_from_admin_settings(monkeypatch):
    FakeSettings.rows = {"seller_rebook_max": 2}
    order("delivery_failed", delivery_method="delivery")

    class Profiles:
        def read_seller_profile_by_user_id(self, _):
            return {"id": "seller"}

    class Deliveries:
        def read_delivery_by_order_id(self, _):
            return {"id": "d1", "status": "REJECTED", "rebook_count": 2}
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", Profiles)
    monkeypatch.setattr(deliveries, "DAOOrders", FakeSellerOrders)
    monkeypatch.setattr(deliveries, "DAODeliveries", Deliveries)
    with pytest.raises(HTTPException) as e:
        deliveries.rebook_delivery("o1", user={"id": "s"})
    assert (e.value.status_code, e.value.detail) == (400, "Max rebook attempts reached")


def test_r6_1_delivery_failed_29_min_refused():
    order("delivery_failed", status_changed_at=ago(minutes=29))
    assert assert_refused() == "delivery_failed"


def test_r6_2_delivery_failed_31_min_cancels_with_refund():
    order("delivery_failed", status_changed_at=ago(minutes=31))
    assert_late_cancel()


def test_r6_4_rebooked_order_has_no_cancel_deadline():
    # Rebook moves the order back to ready (and resets status_changed_at in the DB trigger)
    assert orders.cancel_after({"status": "ready", "status_changed_at": ago(hours=2)}) is None


def test_windows_come_from_admin_settings():
    FakeSettings.rows = {"buyer_cancel_late_confirmed_minutes": 90,
                         "buyer_cancel_late_delivery_failed_minutes": 45,
                         "buyer_cancel_before_appointment_minutes": 120}
    order("confirmed", status_changed_at=ago(minutes=61))
    assert assert_refused() == "confirmed"              # 61 < 90
    order("delivery_failed", status_changed_at=ago(minutes=31))
    assert assert_refused() == "delivery_failed"        # 31 < 45
    soon = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    order("pending", delivery_appointment=soon)
    assert buyer_cancel()["success"]                    # 3 h ahead > 2 h cutoff (default 24 h would refuse)


def test_appointment_cutoff_default_24h():
    soon = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()
    order("pending", delivery_appointment=soon)
    assert assert_refused() == "pending"                # R3.3


def test_invalid_setting_falls_back_to_default():
    from dao.dao_admin_config import DAOAdminConfig
    for bad in (None, 0, -5, "abc", True, 1.5):
        dao = DAOAdminConfig.__new__(DAOAdminConfig)    # skip __init__: no Supabase client
        dao.get_setting = lambda key, v=bad: v
        assert dao.get_minutes("k", 60) == timedelta(minutes=60)
    dao.get_setting = lambda key: 90
    assert dao.get_minutes("k", 60) == timedelta(minutes=90)


def test_pending_cancel_unchanged():
    order("pending")
    assert buyer_cancel()["success"]
    assert FakeOrders.row["cancellation_reason"] is None
    assert refunds == [("o1", "buyer_cancel", 125000)]


# T129: GET /orders/{id} gives the last moment a pending scheduled order may be cancelled, from the same
# cancel_before() the cancel API checks, so the app shows "Cancel" only while it is allowed.
def order_detail(monkeypatch):
    monkeypatch.setattr(orders, "complaints_for_order", lambda o, uid, role: {})
    return orders.get_order_detail("o1", user={"id": "buyer"})["order"]


def test_t129_scheduled_more_than_24h_ahead_gives_the_cutoff(monkeypatch):
    appointment = datetime.now(timezone.utc) + timedelta(hours=30)
    order("pending", delivery_appointment=appointment.isoformat())
    assert datetime.fromisoformat(order_detail(monkeypatch)["cancel_before"]) == appointment - timedelta(hours=24)
    assert buyer_cancel()["success"]


def test_t129_scheduled_less_than_24h_ahead_cutoff_passed(monkeypatch):
    order("pending", delivery_appointment=(datetime.now(timezone.utc) + timedelta(hours=10)).isoformat())
    last = datetime.fromisoformat(order_detail(monkeypatch)["cancel_before"])
    assert last < datetime.now(timezone.utc)            # the app hides Cancel
    assert assert_refused() == "pending"                # and the API agrees


def test_t129_cutoff_follows_admin_settings(monkeypatch):
    FakeSettings.rows = {"buyer_cancel_before_appointment_minutes": 120}
    appointment = datetime.now(timezone.utc) + timedelta(hours=3)
    order("pending", delivery_appointment=appointment.isoformat())
    assert datetime.fromisoformat(order_detail(monkeypatch)["cancel_before"]) == appointment - timedelta(hours=2)


def test_t129_no_cutoff_for_asap_or_accepted_orders(monkeypatch):
    order("pending")                                     # deliver now: cancel any time before acceptance
    assert order_detail(monkeypatch)["cancel_before"] is None
    order("confirmed", delivery_appointment=(datetime.now(timezone.utc) + timedelta(hours=30)).isoformat())
    assert order_detail(monkeypatch)["cancel_before"] is None
