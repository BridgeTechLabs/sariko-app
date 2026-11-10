"""T161 AllinGo, a second delivery company behind admin_settings delivery_provider_allingo
(docs/dev/20261109-allingo-delivery). AllinGo's HTTP is faked at requests.request, so the real
AllingoService builds every body, header and token. No DB, no network."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests
from fastapi import HTTPException

import dao.dao_deliveries
import dao.dao_refunds
from apis import deliveries, orders, sellers
from schemas import Schema
from services import allingo_service, push_service

OID = "11111111-1111-4111-8111-111111111111"
BASE = "https://pro.allingo.vn/api/v1"
SECRET = "whsec_test"


def reply(status, body=None):
    text = json.dumps(body) if body is not None else ""
    return SimpleNamespace(status_code=status, ok=200 <= status < 300, text=text, json=lambda: json.loads(text))


def quote(price, service_id=None, available=True, driver_info=True):
    return {"service_id": service_id or f"svc{price}", "price": price, "currency": "VND", "available": available,
            "tracking": {"driver_info": driver_info}}


def trip(trip_id="ord_1", status="queued", leg="queued", cod=0):
    return {"id": trip_id, "status": status, "external_reference": OID, "fee": {"cod": cod, "total": 34800},
            "delivery": {"status": leg, "track_link": f"https://business.allingo.vn/track/{trip_id}"}}


class FakeHTTP:
    """routes[(method, path)] = a reply, an exception, or a list of them used in turn."""

    def __init__(self):
        self.calls, self.tokens = [], 0
        self.routes = {("POST", "/inquiries"): reply(200, {"quotes": [quote(41000), quote(34800)]}),
                       ("GET", "/orders"): reply(200, {"data": [], "has_more": False}),
                       ("POST", "/orders"): reply(201, trip()),
                       ("POST", "/orders/ord_1/cancel"): reply(200, {"id": "ord_1", "status": "canceled", "refunded_amount": 34800})}

    def __call__(self, method, url, json=None, params=None, headers=None, timeout=None):
        path = url.replace(BASE, "")
        if path == "/oauth/token":
            self.tokens += 1
            return reply(200, {"access_token": f"tok{self.tokens}", "expires_in": 3600})
        self.calls.append(SimpleNamespace(method=method, path=path, json=json, params=params, headers=headers))
        answer = self.routes[(method, path)]
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def made(self, method, path):
        return [c for c in self.calls if (c.method, c.path) == (method, path)]


@pytest.fixture
def http(monkeypatch):
    """Switch = 1 (AllinGo), test keys in env, AllinGo answered by FakeHTTP."""
    monkeypatch.setenv("ALLINGO_APP_ID", "app_test_x")
    monkeypatch.setenv("ALLINGO_APP_SECRET", "sk_test_x")
    monkeypatch.delenv("ALLINGO_PARTNER_IDS", raising=False)
    allingo_service.reset_allingo_service()
    fake = FakeHTTP()
    monkeypatch.setattr(allingo_service.requests, "request", fake)
    monkeypatch.setattr(allingo_service, "enabled", lambda: True)
    yield fake
    allingo_service.reset_allingo_service()


@pytest.fixture
def admin_pushes(monkeypatch):
    sent = []
    monkeypatch.setattr(push_service, "notify_admins", lambda event, url, **f: sent.append((event, url, f)))
    return sent


PICKUP = allingo_service.address("Q1", 10.77, 106.70)
DROPOFF = allingo_service.address("D7", 10.73, 106.72)


# ── TC-2, TC-10, TC-24: the service ─────────────────────────────────────────

def test_tc2_inquiry_body_never_cash_and_cheapest_usable_quote(http, monkeypatch):
    http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [
        quote(20000, available=False), quote(25000, driver_info=False), quote(41000), quote(34800, "first"), quote(34800, "second")]})
    result = allingo_service.get_allingo_service().quote(PICKUP, DROPOFF)
    body = http.made("POST", "/inquiries")[0].json
    assert {k: body[k] for k in ("cod_amount", "delivery_payment_method", "payee", "type")} == \
        {"cod_amount": 0, "delivery_payment_method": "credit", "payee": "sender", "type": "on_demand"}
    assert body["filter_partner_ids"] == ["grab", "lalamove", "gsm"]
    assert (result.quotation_id, result.total_fee) == ("first", 34800)   # cheapest usable; equal price -> first

    monkeypatch.setenv("ALLINGO_PARTNER_IDS", "simulator")
    allingo_service.reset_allingo_service()
    allingo_service.get_allingo_service().quote(PICKUP, DROPOFF)
    assert http.made("POST", "/inquiries")[-1].json["filter_partner_ids"] == ["simulator"]


def test_tc2_quickstart_shape_and_no_usable_quote(http):
    http.routes[("POST", "/inquiries")] = reply(200, {"quotes": {"data": [quote(30000)]}})
    assert allingo_service.get_allingo_service().quote(PICKUP, DROPOFF).total_fee == 30000
    http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [quote(30000, driver_info=False)]})
    with pytest.raises(allingo_service.AllingoError) as e:
        allingo_service.get_allingo_service().quote(PICKUP, DROPOFF)
    assert e.value.code == "allingo_no_quote"


def test_tc10_token_cached_and_renewed_under_5_minutes(http):
    service = allingo_service.get_allingo_service()
    service.quote(PICKUP, DROPOFF)
    service.quote(PICKUP, DROPOFF)
    assert http.tokens == 1
    service._token_until = time.time() + 299
    service.quote(PICKUP, DROPOFF)
    assert http.tokens == 2 and http.calls[-1].headers["Authorization"] == "Bearer tok2"


def test_tc24_401_renews_token_once(http):
    service = allingo_service.get_allingo_service()
    http.routes[("POST", "/inquiries")] = [reply(401, {}), reply(200, {"quotes": [quote(30000)]})]
    assert service.quote(PICKUP, DROPOFF).total_fee == 30000
    assert http.tokens == 2
    http.routes[("POST", "/inquiries")] = reply(401, {})
    with pytest.raises(allingo_service.AllingoError) as e:
        service.quote(PICKUP, DROPOFF)
    assert e.value.code == "allingo_unauthorized" and http.tokens == 3   # one new token, then give up


@pytest.mark.parametrize("answer", [{"id": "ord_1", "status": "canceled", "refunded_amount": 34800},
                                    {"id": "ord_1", "status": "canceled", "canceled_at": None, "refund": None}])
def test_tc24_cancel_takes_both_answer_shapes(http, answer):
    http.routes[("POST", "/orders/ord_1/cancel")] = reply(200, answer)
    assert allingo_service.get_allingo_service().cancel_order("ord_1") is True
    http.routes[("POST", "/orders/ord_1/cancel")] = reply(409, {"error": {"code": "cannot_cancel"}})
    assert allingo_service.get_allingo_service().cancel_order("ord_1") is False
    keys = [c.headers["Idempotency-Key"] for c in http.made("POST", "/orders/ord_1/cancel")]
    assert len(set(keys)) == 2   # TC-22: a new key per call


# ── TC-18: the switch ───────────────────────────────────────────────────────

@pytest.mark.parametrize("value, on", [(1, True), (0, False), (2, False), ("abc", False), (None, False), (True, False)])
def test_tc18_switch_values(monkeypatch, value, on):
    from dao.dao_admin_config import DAOAdminConfig
    monkeypatch.undo()   # the conftest default (Lalamove) is what this test checks the real reader against
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, key: value if key == "delivery_provider_allingo" else 1)
    assert allingo_service.enabled() is on


def test_tc18_switch_read_error_is_lalamove(monkeypatch):
    def broken():
        raise RuntimeError("Supabase down")
    monkeypatch.undo()
    monkeypatch.setattr(allingo_service, "DAOAdminConfig", broken)
    assert allingo_service.enabled() is False


# ── TC-3, TC-23: quotes for the cart and create_order ───────────────────────

def test_tc3_tc23_cart_quotation_from_allingo(api, http, monkeypatch):
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(
        read_seller_coords_by_id=lambda sid: {"lat": 10.77, "lon": 106.70, "address": "Q1"}))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: pytest.fail("Lalamove must not be asked"))
    r = api(deliveries.router).post("/deliveries/quotation", json={
        "seller_id": "s1", "delivery_lat": 10.73, "delivery_lon": 106.72, "delivery_address": "D7"})
    assert r.status_code == 200
    assert r.json() == {"success": True, "quotation_id": "svc34800", "stop_id_0": None, "stop_id_1": None,
                        "total_fee": 34800, "currency": "VND", "distance_km": 0}
    assert "contact_phone" not in http.made("POST", "/inquiries")[0].json["dropoff"]   # the cart has no buyer phone


@pytest.mark.parametrize("client_fee, status", [(34800, 200), (30000, 409)])
def test_tc3_tc23_create_order_quotes_allingo(http, monkeypatch, client_fee, status):
    import test_order_delivery_fee as fee_test
    fee_test.created.clear()
    for name, fake in [("DAOCartItems", fee_test.FakeCartItems), ("DAOOrders", fee_test.FakeOrders),
                       ("DAOSellerProfiles", fee_test.FakeSellers), ("DAOAdminConfig", fee_test.FakeVat),
                       ("DAOOrderItems", fee_test.FakeOrderItems), ("DAOCarts", fee_test.FakeCarts)]:
        monkeypatch.setattr(orders, name, fake)
    monkeypatch.setattr(orders, "get_lalamove_service", lambda: pytest.fail("Lalamove must not be asked"))
    req = Schema.RequestCreateOrder(delivery_method="delivery", delivery_address="D7", delivery_lat=10.73, delivery_lon=106.72,
                                    delivery_fee=client_fee, delivery_appointment=datetime.now(timezone.utc) + timedelta(days=2))
    if status == 409:
        with pytest.raises(HTTPException) as e:
            orders.create_order(req, user={"id": "buyer"})
        assert e.value.status_code == 409 and e.value.detail["code"] == "delivery_fee_changed"
        assert e.value.detail["delivery_fee"] == 34800
    else:
        orders.create_order(req, user={"id": "buyer"})
        [order] = fee_test.created
        assert (order["delivery_fee"], order["quotation_id"]) == (34800, "svc34800")


# ── Seller ready / rebook (TC-4, 5, 6, 9, 21, 22, 25, 29) ──────────────────

refunds = []


class Orders:
    row, writes = None, []

    def read_order_by_id_for_seller(self, order_id, seller_id):
        return dict(Orders.row)

    def read_order_with_seller_coords(self, order_id):
        return {**Orders.row, "delivery_address": "D7", "delivery_lat": 10.73, "delivery_lon": 106.72, "delivery_note": "Gate 2",
                "seller_profiles": {"store_name": "Bếp A", "address": "Q1", "lat": 10.77, "lon": 106.70, "phone": "0901234567"},
                "users": {"name": "Buyer", "phone": "0907654321"}}

    def read_order_by_id_raw(self, order_id):
        return dict(Orders.row) if Orders.row and Orders.row["id"] == order_id else None

    def update_order_status(self, order_id, status, cancellation_reason=None, expected_status=None):
        if expected_status and Orders.row["status"] != expected_status:
            return None
        Orders.row = {**Orders.row, "status": status}
        Orders.writes.append(status)
        return dict(Orders.row)

    def touch_order(self, order_id):
        pass


class Deliveries:
    row, created, updates, fail_create = None, [], [], False

    def create_delivery(self, **kw):
        if Deliveries.fail_create:
            raise RuntimeError("insert failed")
        Deliveries.created.append(kw)
        return kw

    def read_delivery_by_order_id(self, order_id):
        return Deliveries.row

    def read_delivery_by_allingo_order_id(self, trip_id):
        return Deliveries.row if Deliveries.row and Deliveries.row.get("allingo_order_id") == trip_id else None

    def read_delivery_by_lalamove_order_id(self, trip_id):
        return Deliveries.row if Deliveries.row and Deliveries.row.get("lalamove_order_id") == trip_id else None

    def update_delivery(self, delivery_id, data):
        Deliveries.updates.append(data)
        Deliveries.row = {**Deliveries.row, **data}


class Settings:
    def get_positive_int(self, key, default):
        return default


class Refunds:
    def create_refund_for_order(self, order, reason):
        refunds.append(reason)


@pytest.fixture
def seller(monkeypatch, http, admin_pushes):
    Orders.row = {"id": OID, "status": "confirmed", "payment_status": "paid", "delivery_method": "delivery",
                  "total_amount": 134800, "delivery_fee": 30000, "user_id": "buyer", "seller_user_id": "seller-user"}
    Orders.writes, Deliveries.row, Deliveries.created, Deliveries.updates, Deliveries.fail_create = [], None, [], [], False
    refunds.clear()
    for module in (sellers, deliveries):
        monkeypatch.setattr(module, "DAOOrders", Orders)
        monkeypatch.setattr(module, "DAOAdminConfig", Settings)
    monkeypatch.setattr(deliveries, "DAODeliveries", Deliveries)
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_profile_by_user_id=lambda u: {"id": "s"}))
    monkeypatch.setattr(dao.dao_deliveries, "DAODeliveries", Deliveries)
    monkeypatch.setattr(dao.dao_refunds, "DAORefunds", Refunds)
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "s")
    monkeypatch.setattr("services.lalamove_service.get_lalamove_service", lambda: pytest.fail("Lalamove must not be called"))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: pytest.fail("Lalamove must not be called"))
    return SimpleNamespace(http=http, admin=admin_pushes)


def mark_ready():
    return sellers.update_seller_order_status(OID, Schema.RequestUpdateOrderStatus(status="ready"), user={"id": "s"})


def booking_failed(e):
    assert e.value.status_code == 503
    assert Orders.row["status"] == "cancelled" and refunds == ["driver_booking_failed"]
    assert "34800" not in str(e.value.detail) and "allingo" not in str(e.value.detail).lower()


def test_tc4_tc25_ready_books_allingo_paid_from_the_wallet(seller):
    assert mark_ready()["order"]["status"] == "ready"
    [post] = seller.http.made("POST", "/orders")
    body = post.json
    assert {k: body[k] for k in ("cod_amount", "delivery_payment_method", "payee", "deliverable_payment_method", "type")} == \
        {"cod_amount": 0, "delivery_payment_method": "credit", "payee": "sender", "deliverable_payment_method": "prepaid", "type": "on_demand"}
    # TC-25: the price just quoted, not the 30.000 ₫ the buyer paid; Sariko carries the difference
    assert (body["estimated_price"], body["service_id"], body["external_reference"]) == (34800, "svc34800", OID)
    assert body["pickup"]["contact_phone"] == "+84901234567" and body["dropoff"]["contact_phone"] == "+84907654321"
    assert body["dropoff"]["note"] == "Gate 2 | D7"
    assert post.headers["Idempotency-Key"].startswith(f"sariko-{OID}-")
    assert seller.http.made("GET", "/orders")[0].params == {"external_reference": OID}
    [row] = Deliveries.created
    assert row["provider"] == "allingo" and row["allingo_order_id"] == "ord_1" and row["lalamove_order_id"] is None
    assert (row["status"], row["share_link"]) == ("ASSIGNING_DRIVER", "https://business.allingo.vn/track/ord_1")


def test_tc4_tc22_timeout_then_lookup_finds_the_trip_no_second_post(seller):
    seller.http.routes[("POST", "/orders")] = requests.Timeout("read timeout")
    seller.http.routes[("GET", "/orders")] = [reply(200, {"data": []}),
                                              reply(200, {"data": [trip("ord_old", "canceled", "canceled"), trip("ord_9")]})]
    mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 1
    assert Deliveries.created[0]["allingo_order_id"] == "ord_9"


def test_tc4_tc22_retry_after_5xx_uses_a_new_key(seller):
    seller.http.routes[("POST", "/orders")] = [reply(503, {"error": {"code": "partner_unavailable"}}), reply(201, trip())]
    mark_ready()
    keys = [c.headers["Idempotency-Key"] for c in seller.http.made("POST", "/orders")]
    assert len(keys) == 2 and keys[0] != keys[1]
    assert len(seller.http.made("GET", "/orders")) == 2   # looked up before every try


def test_tc4_4xx_is_not_retried(seller):
    seller.http.routes[("POST", "/orders")] = reply(422, {"error": {"code": "validation_failed"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 1
    booking_failed(e)


def test_tc5_empty_wallet_at_ready(seller):
    seller.http.routes[("POST", "/orders")] = reply(402, {"error": {"code": "insufficient_wallet_credit",
                                                                    "message": "Required: 34800, Available: 0"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 1
    assert seller.admin == [("admin_delivery_wallet_empty", f"/orders?open={OID}", {"code": OID[:8]})]
    booking_failed(e)


def test_tc6_cod_on_the_trip_cancels_it(seller):
    seller.http.routes[("POST", "/orders")] = reply(201, trip(cod=34800))
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert len(seller.http.made("POST", "/orders/ord_1/cancel")) == 1 and Deliveries.created == []
    booking_failed(e)


def test_tc9_insert_failure_cancels_the_allingo_trip(seller):
    Deliveries.fail_create = True
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 500 and len(seller.http.made("POST", "/orders/ord_1/cancel")) == 1


def rebook():
    return deliveries.rebook_delivery(OID, user={"id": "s"})


def test_tc9_rebook_lalamove_row_to_allingo(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "lalamove", "lalamove_order_id": "LM1", "status": "EXPIRED",
                      "rebook_count": 1, "driver_name": "A"}
    assert rebook() == {"success": True}
    [update] = Deliveries.updates
    assert update == {"provider": "allingo", "allingo_order_id": "ord_1", "lalamove_order_id": None, "status": "ASSIGNING_DRIVER",
                      "share_link": "https://business.allingo.vn/track/ord_1", "driver_name": None, "driver_phone": None,
                      "driver_plate": None, "rebook_count": 2}
    assert Orders.row["status"] == "ready"


def test_tc9_rebook_allingo_row_to_lalamove(seller, monkeypatch):
    monkeypatch.setattr(allingo_service, "enabled", lambda: False)
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_1", "status": "CANCELED", "rebook_count": 0}
    lalamove = SimpleNamespace(
        get_quotation=lambda **kw: SimpleNamespace(quotation_id="Q", stop_id_0="a", stop_id_1="b"),
        place_order=lambda **kw: SimpleNamespace(status="ASSIGNING_DRIVER", lalamove_order_id="LM2", share_link="https://ll"))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: lalamove)
    rebook()
    [update] = Deliveries.updates
    assert (update["provider"], update["lalamove_order_id"], update["allingo_order_id"]) == ("lalamove", "LM2", None)


def test_tc21_tc22_empty_wallet_at_rebook_keeps_the_order(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    seller.http.routes[("POST", "/orders")] = reply(402, {"error": {"code": "wallet_insufficient", "message": "Required: 34800, Available: 0"}})
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 503
    assert "34800" not in str(e.value.detail) and "allingo" not in str(e.value.detail).lower()
    assert Orders.row["status"] == "delivery_failed" and Orders.writes == [] and refunds == []
    assert [a[0] for a in seller.admin] == ["admin_delivery_wallet_empty"]
    # Wallet topped up: the next tap books with a new key, not the stored 402
    seller.http.routes[("POST", "/orders")] = reply(201, trip())
    assert rebook() == {"success": True}
    keys = [c.headers["Idempotency-Key"] for c in seller.http.made("POST", "/orders")]
    assert len(set(keys)) == 2


def test_tc29_rebook_takes_a_running_trip_not_an_ended_one(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip("ord_0", "canceled", "canceled"),
                                                                  trip("ord_c", "completed", "completed"),
                                                                  trip("ord_f", "return_finished", "return_finished"),
                                                                  trip("ord_x", "on_going", "failed"),          # QA 3: order
                                                                  trip("ord_r", "on_going", "return_active")]})  # still on_going
    rebook()   # (b) only ended trips -> a new one is booked
    assert len(seller.http.made("POST", "/orders")) == 1 and Deliveries.row["allingo_order_id"] == "ord_1"

    Orders.row["status"], Deliveries.row["status"] = "delivery_failed", "CANCELED"
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip("ord_live", "on_going", "courier_assigned")]})
    rebook()   # (a) a timed-out tap made one -> taken, no second POST; (c) its row is built
    assert len(seller.http.made("POST", "/orders")) == 1
    assert {k: Deliveries.row[k] for k in ("allingo_order_id", "status", "share_link")} == \
        {"allingo_order_id": "ord_live", "status": "ON_GOING", "share_link": "https://business.allingo.vn/track/ord_live"}


def test_a22c_lost_trip_cannot_be_rebooked(seller):   # T177 TC-A22c
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "LOST", "rebook_count": 0}
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 409 and e.value.detail["code"] == "delivery_lost"
    assert seller.http.made("POST", "/orders") == [] and Deliveries.updates == [] and Orders.writes == []


@pytest.mark.parametrize("status, reason", [("delivery_failed", "driver_booking_failed"),   # T177 TC-A32a: no rider
                                            ("confirmed", "seller_cancel"), ("pending", "seller_cancel")])
def test_a32a_seller_cancel_reason(seller, status, reason):
    Orders.row["status"] = status
    sellers.update_seller_order_status(OID, Schema.RequestUpdateOrderStatus(status="cancelled", cancellation_reason="No rider"),
                                       user={"id": "s"})
    assert Orders.row["status"] == "cancelled" and refunds == [reason]


def test_a32b_auto_cancel_does_not_overwrite_another_cancel(seller, monkeypatch):   # T177 TC-A32b
    seller.http.routes[("POST", "/orders")] = reply(422, {"error": {"code": "validation_failed"}})
    real = Orders.read_order_by_id_for_seller

    def read_then_buyer_cancels(self, order_id, seller_id):
        snapshot = real(self, order_id, seller_id)
        Orders.row = {**Orders.row, "status": "cancelled"}   # the buyer cancelled while the booking ran
        return snapshot
    monkeypatch.setattr(Orders, "read_order_by_id_for_seller", read_then_buyer_cancels)
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 409
    assert Orders.row["status"] == "cancelled" and Orders.writes == [] and refunds == []


@pytest.mark.parametrize("provider", ["allingo", "lalamove", None])
def test_tc9_tc18_buyer_cancel_goes_to_the_trip_company(seller, monkeypatch, provider):
    cancelled = []
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: SimpleNamespace(cancel_order=lambda i: cancelled.append(i) or True))
    monkeypatch.setattr(deliveries, "DAOOrders", lambda: SimpleNamespace(read_order_by_id=lambda oid, uid: {"id": OID},
                                                                         touch_order=lambda oid: None))
    Deliveries.row = {"id": "d1", "provider": provider, "allingo_order_id": "ord_1" if provider == "allingo" else None,
                      "lalamove_order_id": None if provider == "allingo" else "LM1", "status": "ASSIGNING_DRIVER"}
    assert deliveries.cancel_delivery(OID, user={"id": "buyer"}) == {"success": True}
    assert len(seller.http.made("POST", "/orders/ord_1/cancel")) == (provider == "allingo")
    assert cancelled == ([] if provider == "allingo" else ["LM1"])


# ── Webhook (TC-7, 8, 16, 17, 19, 20, 30) ───────────────────────────────────

def event(leg_status, trip_id="ord_1", kind="delivery.status_changed", driver=None, ref=OID):
    obj = {"id": trip_id, "external_reference": ref,
           "delivery": {"status": leg_status, "track_link": f"https://business.allingo.vn/track/{trip_id}", "driver": driver}}
    return {"id": "evt_1", "type": kind, "livemode": False, "data": {"object": obj}}


def post_event(client, body, secret=SECRET, t=None):
    raw = json.dumps(body).encode()
    t = int(time.time()) if t is None else t
    v1 = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return client.post("/deliveries/webhook/allingo", content=raw,
                       headers={"X-AllinGo-Signature": f"t={t},v1={v1}", "Content-Type": "application/json"})


@pytest.fixture
def hook(monkeypatch, admin_pushes, fastapi_client):
    monkeypatch.setenv("ALLINGO_WEBHOOK_SECRET", SECRET)
    Orders.row = {"id": OID, "status": "ready", "seller_user_id": "seller-user"}
    Orders.writes, Deliveries.updates = [], []
    Deliveries.row = {"id": "d1", "order_id": OID, "provider": "allingo", "allingo_order_id": "ord_1",
                      "status": "ASSIGNING_DRIVER", "share_link": "https://business.allingo.vn/track/ord_1"}
    monkeypatch.setattr(deliveries, "DAOOrders", Orders)
    monkeypatch.setattr(deliveries, "DAODeliveries", Deliveries)
    pushes = []
    monkeypatch.setattr(push_service, "notify_seller_delivered", lambda o: pushes.append("delivered"))
    monkeypatch.setattr(push_service, "notify_seller_driver_assigned", lambda o: pushes.append("driver"))
    return SimpleNamespace(client=fastapi_client, pushes=pushes, admin=admin_pushes)


def test_tc7_signature(hook, monkeypatch):
    assert post_event(hook.client, event("queued")).status_code == 200
    assert post_event(hook.client, event("queued"), secret="other").status_code == 401
    assert post_event(hook.client, event("queued"), t=int(time.time()) - 301).status_code == 401
    assert hook.client.post("/deliveries/webhook/allingo", json=event("completed")).status_code == 401   # unsigned
    monkeypatch.setenv("ALLINGO_WEBHOOK_SECRET", "")
    assert post_event(hook.client, event("completed")).status_code == 503
    assert Orders.writes == []


@pytest.mark.parametrize("leg, stored", [
    ("pending_schedule", "ASSIGNING_DRIVER"), ("courier_assigned", "ON_GOING"), ("courier_at_origin", "ON_GOING"),
    ("picked_up", "PICKED_UP"), ("in_transit", "PICKED_UP"), ("courier_waiting_at_destination", "PICKED_UP"),
    ("completed", "COMPLETED"), ("canceled", "CANCELED"), ("failed", "CANCELED"), ("return_finished", "CANCELED"),
    ("lost", "CANCELED"), ("damaged", "CANCELED"), ("pickup_failed", "ON_GOING"),
    ("deliver_failed", "ON_GOING"), ("something_new", "ON_GOING")])
def test_tc8_status_map(hook, leg, stored):
    if stored == "ON_GOING":   # retry states and unknown values keep what is stored
        Deliveries.row["status"] = "ON_GOING"
    assert post_event(hook.client, event(leg)).status_code == 200
    assert Deliveries.row["status"] == stored


def test_tc8_completed_done_once_and_canceled_fails_the_order(hook):
    for _ in range(2):
        post_event(hook.client, event("completed"))
    assert Orders.row["status"] == "done" and hook.pushes == ["delivered"]

    Orders.row["status"] = "ready"
    Deliveries.row = {**Deliveries.row, "status": "ON_GOING", "driver_phone": "+849", "driver_plate": "59A"}
    post_event(hook.client, event("canceled"))
    assert Orders.row["status"] == "delivery_failed"
    assert [a[0] for a in hook.admin] == ["admin_delivery_failed"]
    assert Deliveries.row["driver_phone"] is None and Deliveries.row["share_link"] is None


@pytest.mark.parametrize("leg", ["failed", "return_active", "return_finished", "lost", "damaged"])
def test_a22_failure_after_pickup_is_lost(hook, leg):   # T177 TC-A22a / A22b
    Deliveries.row = {**Deliveries.row, "status": "PICKED_UP", "driver_phone": "+849", "driver_plate": "59A"}
    for _ in range(2):   # AllinGo retries the event: one order change, one push
        assert post_event(hook.client, event(leg)).status_code == 200
    assert Deliveries.row["status"] == "LOST" and Deliveries.row["driver_phone"] is None
    assert Orders.row["status"] == "delivery_failed"
    assert [a[0] for a in hook.admin] == ["admin_delivery_lost"]
    post_event(hook.client, event("in_transit"))   # an older event arriving late does not reopen the trip
    assert Deliveries.row["status"] == "LOST"


def test_tc8_older_event_does_not_win(hook):
    post_event(hook.client, event("picked_up"))
    post_event(hook.client, event("courier_assigned"))
    assert Deliveries.row["status"] == "PICKED_UP"


def test_tc8_tc20_driver_push_only_for_a_new_driver(hook):
    a = {"name": "A", "phone": "+84900000001", "license_plate": "59A-1"}
    b = {"name": "B", "phone": "+84900000002", "license_plate": "59B-2"}
    post_event(hook.client, event("courier_assigned", kind="delivery.driver_assigned", driver=a))
    assert (Deliveries.row["driver_name"], Deliveries.row["driver_plate"]) == ("A", "59A-1") and hook.pushes == ["driver"]
    post_event(hook.client, event("courier_to_origin", driver=a))           # same driver again
    assert hook.pushes == ["driver"]
    body = event("courier_assigned", kind="delivery.driver_assigned")
    body["data"]["driver"] = b                                             # driver in data.driver, a replacement
    post_event(hook.client, body)
    assert Deliveries.row["driver_name"] == "B" and hook.pushes == ["driver", "driver"]
    assert Orders.writes == []


@pytest.mark.parametrize("ended", ["CANCELLED", "REJECTED", "EXPIRED", "COMPLETED", "CANCELED"])
@pytest.mark.parametrize("leg", ["queued", "picked_up", "completed", "canceled"])
def test_tc20_nothing_moves_after_an_end(hook, ended, leg):
    Orders.row["status"] = "done" if ended == "COMPLETED" else "delivery_failed"
    Deliveries.row["status"] = ended
    post_event(hook.client, event(leg))
    assert Deliveries.row["status"] == ended and Deliveries.updates == []
    assert Orders.row["status"] in ("done", "delivery_failed")


def test_tc16_retry_after_a_failure_finishes_the_order(hook, monkeypatch):
    real = Orders.update_order_status
    calls = []

    def flaky(self, *args, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("DB down")
        return real(self, *args, **kw)
    monkeypatch.setattr(Orders, "update_order_status", flaky)
    assert post_event(hook.client, event("completed")).status_code == 500
    assert Deliveries.row["status"] == "COMPLETED" and Orders.row["status"] == "ready"
    assert post_event(hook.client, event("completed")).status_code == 200
    assert Orders.row["status"] == "done" and hook.pushes == ["delivered"]


@pytest.mark.parametrize("order_status, done", [("cancelled", False), ("ready", True), ("delivery_failed", True)])
def test_tc30_completed_moves_only_ready_or_failed_orders(hook, order_status, done):
    Orders.row["status"] = order_status
    post_event(hook.client, event("completed"))
    assert (Orders.row["status"] == "done") is done


def test_tc17_late_event_of_the_other_company_is_ignored(hook, fastapi_client, lalamove_secret, lalamove_api_key):
    # Lalamove LM1 was rebooked to AllinGo: Lalamove's late CANCELLED for LM1 changes nothing
    Deliveries.row = {**Deliveries.row, "lalamove_order_id": "LM1", "status": "ON_GOING"}
    data, ts = {"order": {"orderId": "LM1", "status": "CANCELLED"}}, 1735689600000
    signed = f"{ts}\r\nPOST\r\n/deliveries/webhook\r\n\r\n{json.dumps(data, separators=(',', ':'))}"
    raw = json.dumps({"apiKey": lalamove_api_key, "timestamp": ts, "eventType": "ORDER_STATUS_CHANGED", "data": data,
                      "signature": hmac.new(lalamove_secret.encode(), signed.encode(), hashlib.sha256).hexdigest()},
                     separators=(",", ":"))
    assert fastapi_client.post("/deliveries/webhook", content=raw, headers={"Content-Type": "application/json"}).json() == {"success": True}
    # AllinGo ord_old was rebooked to Lalamove (allingo_order_id cleared): its late canceled changes nothing
    Deliveries.row = {**Deliveries.row, "provider": "lalamove", "allingo_order_id": None}
    assert post_event(hook.client, event("canceled", trip_id="ord_old")).status_code == 200
    # Even a row still holding the AllinGo id is skipped once its provider is Lalamove
    Deliveries.row["allingo_order_id"] = "ord_old"
    assert post_event(hook.client, event("canceled", trip_id="ord_old")).status_code == 200
    assert Deliveries.updates == [] and Orders.writes == [] and Deliveries.row["status"] == "ON_GOING"


def test_tc19_event_before_the_row_is_written(hook):
    Deliveries.row = None
    Orders.row["status"] = "confirmed"   # Ready is booking: trip made, row not inserted yet
    assert post_event(hook.client, event("courier_assigned", trip_id="ord_new")).status_code == 503
    assert post_event(hook.client, event("courier_assigned", trip_id="ord_x", ref="TEST-trial")).status_code == 200
    Orders.row = None
    assert post_event(hook.client, event("courier_assigned", trip_id="ord_new")).status_code == 200


def test_unexpected_error_answers_500(hook, monkeypatch):
    monkeypatch.setattr(Deliveries, "update_delivery", lambda self, i, d: 1 / 0)
    assert post_event(hook.client, event("picked_up")).status_code == 500


# ── QA nhóm 1 vòng 1: double Ready tap, failed quote, lookup log (TC-31 auto) ─

def test_qa2_double_ready_keeps_the_trip_and_one_row(seller, monkeypatch):
    """Tap A booked ord_1, wrote its row and moved the order to ready; tap B read the order while still confirmed."""
    Orders.row["status"] = "ready"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_1", "status": "ASSIGNING_DRIVER"}
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip()]})
    monkeypatch.setattr(Orders, "read_order_by_id_for_seller", lambda self, oid, sid: {**Orders.row, "status": "confirmed"})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 409
    assert seller.http.made("POST", "/orders") == [] and seller.http.made("POST", "/orders/ord_1/cancel") == []
    assert Deliveries.created == [] and Orders.row["status"] == "ready" and refunds == []


def test_qa2_taken_trip_of_a_cancelled_order_is_cancelled(seller, monkeypatch):
    Orders.row["status"] = "cancelled"   # the buyer cancelled between the two taps
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip()]})
    monkeypatch.setattr(Orders, "read_order_by_id_for_seller", lambda self, oid, sid: {**Orders.row, "status": "confirmed"})
    with pytest.raises(HTTPException):
        mark_ready()
    assert len(seller.http.made("POST", "/orders/ord_1/cancel")) == 1


@pytest.mark.parametrize("answer", [reply(200, {"quotes": []}), requests.ConnectionError("down")])
def test_qa4_failed_quote_keeps_the_order(seller, answer):
    seller.http.routes[("POST", "/inquiries")] = answer
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 502
    assert Orders.row["status"] == "confirmed" and Orders.writes == [] and refunds == []
    assert seller.http.made("POST", "/orders") == [] and Deliveries.created == []
    Orders.row["status"] = "delivery_failed"   # same at rebook
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 502 and Orders.row["status"] == "delivery_failed" and Deliveries.updates == []


@pytest.mark.parametrize("answer", [reply(200, {"orders": []}), reply(500, {})])
def test_tc31_lookup_trouble_is_logged_and_booking_goes_on(seller, caplog, answer):
    seller.http.routes[("GET", "/orders")] = answer
    mark_ready()
    assert "lookup of trips" in caplog.text and len(seller.http.made("POST", "/orders")) == 1
