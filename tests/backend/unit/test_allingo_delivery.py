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
from dao.dao_admin_config import DAOAdminConfig
from schemas import Schema
from services import allingo_service, push_service

OID = "11111111-1111-4111-8111-111111111111"
BASE = "https://pro.allingo.vn/api/v1"
SECRET = "whsec_test"


def reply(status, body=None, headers=None):
    text = json.dumps(body) if body is not None else ""
    return SimpleNamespace(status_code=status, ok=200 <= status < 300, text=text, json=lambda: json.loads(text),
                           headers=headers or {})


def quote(price, service_id=None, available=True, driver_info=True, partner="grab"):
    return {"service_id": service_id or f"svc{price}", "price": price, "currency": "VND", "available": available,
            "tracking": {"driver_info": driver_info}, "partner": {"id": partner, "name": partner}}


def trip(trip_id="ord_1", status="queued", leg="queued", cod=0):
    return {"id": trip_id, "status": status, "external_reference": OID, "fee": {"cod": cod, "total": 34800},
            "delivery": {"status": leg, "track_link": f"https://business.allingo.vn/track/{trip_id}"}}


class FakeHTTP:
    """routes[(method, path)] = a reply, an exception, or a list of them used in turn."""

    def __init__(self):
        self.calls, self.tokens, self.waits = [], 0, []
        self.now, self.cost, self.token_reply = 0.0, 0, None   # T191: a fake clock, seconds per call, a refused token
        self.routes = {("POST", "/inquiries"): reply(200, {"quotes": [quote(41000), quote(34800)]}),
                       ("GET", "/orders"): reply(200, {"data": [], "has_more": False}),
                       ("POST", "/orders"): reply(201, trip()),
                       ("POST", "/orders/ord_1/cancel"): reply(200, {"id": "ord_1", "status": "canceled", "refunded_amount": 34800})}

    def __call__(self, method, url, json=None, params=None, headers=None, timeout=None):
        path = url.replace(BASE, "")
        self.now += self.cost
        if path == "/oauth/token":
            self.tokens += 1
            return self.token_reply or reply(200, {"access_token": f"tok{self.tokens}", "expires_in": 3600})
        self.calls.append(SimpleNamespace(method=method, path=path, json=json, params=params, headers=headers))
        answer = self.routes[(method, path)]
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def made(self, method, path):
        return [c for c in self.calls if (c.method, c.path) == (method, path)]


class SettingsRows(DAOAdminConfig):
    """admin_settings rows for the real get_int_in_range (T192: the company switches); rows = "down" raises."""
    rows = {}

    def __init__(self):
        pass

    def get_setting(self, key):
        if SettingsRows.rows == "down":
            raise RuntimeError("Supabase down")
        return SettingsRows.rows.get(key)


@pytest.fixture
def http(monkeypatch):
    """Switch = 1 (AllinGo), test keys in env, AllinGo answered by FakeHTTP."""
    monkeypatch.setenv("ALLINGO_APP_ID", "app_test_x")
    monkeypatch.setenv("ALLINGO_APP_SECRET", "sk_test_x")
    monkeypatch.delenv("ALLINGO_PARTNER_IDS", raising=False)
    allingo_service.reset_allingo_service()
    fake = FakeHTTP()
    monkeypatch.setattr(allingo_service.requests, "request", fake)
    monkeypatch.setattr(allingo_service, "time", SimpleNamespace(time=time.time, sleep=fake.sleep, monotonic=lambda: fake.now))
    monkeypatch.setattr(allingo_service, "enabled", lambda: True)
    monkeypatch.setattr(allingo_service, "DAOAdminConfig", SettingsRows)
    SettingsRows.rows = {"allingo_partner_grab": 1, "allingo_partner_gsm": 1, "allingo_partner_lalamove": 0}
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
    assert body["filter_partner_ids"] == ["grab", "gsm"]   # T192: the switches' defaults, no Lalamove through AllinGo
    assert (result.quotation_id, result.total_fee) == ("first", 34800)   # cheapest usable; equal price -> first

    monkeypatch.setenv("ALLINGO_PARTNER_IDS", "simulator")
    http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [quote(30000, partner="simulator")]})
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
    assert e.value.code == "allingo_blocked" and http.tokens == 3   # one new token, then give up


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

def cart_seller(monkeypatch, buyer_phone="0907654321"):
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_coords_by_id=lambda sid: {
        "lat": 10.77, "lon": 106.70, "address": "Q1", "store_name": "Bếp A", "phone": "0901234567"}))
    monkeypatch.setattr(deliveries, "DAOUsers", lambda: SimpleNamespace(
        get_users=lambda uid: {"u1": {"name": "Buyer", "phone": buyer_phone, "email": "b@x.vn"}}.get(uid)))


def post_quotation(api):
    return api(deliveries.router).post("/deliveries/quotation", json={
        "seller_id": "s1", "delivery_lat": 10.73, "delivery_lon": 106.72, "delivery_address": "D7"})


def test_tc3_tc23_cart_quotation_from_allingo(api, http, monkeypatch):
    cart_seller(monkeypatch)
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: pytest.fail("Lalamove must not be asked"))
    r = post_quotation(api)
    assert r.status_code == 200
    assert r.json() == {"success": True, "quotation_id": "svc34800", "stop_id_0": None, "stop_id_1": None,
                        "total_fee": 34800, "currency": "VND", "distance_km": 0}
    # T191 TC-1: an AllinGo Address needs contact_name + contact_phone (docs inquiries.md, Address required)
    body = http.made("POST", "/inquiries")[0].json
    assert (body["pickup"]["contact_name"], body["pickup"]["contact_phone"]) == ("Bếp A", "+84901234567")
    assert (body["dropoff"]["contact_name"], body["dropoff"]["contact_phone"]) == ("Buyer", "+84907654321")


def fake_create_order(monkeypatch):
    """create_order with no DB: the fakes of test_order_delivery_fee."""
    import test_order_delivery_fee as fee_test
    for name, fake in [("DAOCartItems", fee_test.FakeCartItems), ("DAOOrders", fee_test.FakeOrders),
                       ("DAOSellerProfiles", fee_test.FakeSellers), ("DAOAdminConfig", fee_test.FakeVat),
                       ("DAOOrderItems", fee_test.FakeOrderItems), ("DAOCarts", fee_test.FakeCarts)]:
        monkeypatch.setattr(orders, name, fake)
    return fee_test


@pytest.mark.parametrize("client_fee, status", [(34800, 200), (30000, 409)])
def test_tc3_tc23_create_order_quotes_allingo(http, monkeypatch, client_fee, status):
    fee_test = fake_create_order(monkeypatch)
    fee_test.created.clear()
    monkeypatch.setattr(orders, "get_lalamove_service", lambda: pytest.fail("Lalamove must not be asked"))
    monkeypatch.setattr(deliveries, "DAOUsers", lambda: SimpleNamespace(get_users=lambda uid: {"name": "Buyer", "phone": "0907654321"}))
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

    def update_order_status(self, order_id, status, cancellation_reason=None, expected_status=None, cancellation_note=None):
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
            raise RuntimeError(Deliveries.fail_create if isinstance(Deliveries.fail_create, str) else "insert failed")
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


def test_t180_a26b_second_ready_at_once_keeps_one_trip(seller):
    """The DB keeps one live trip per order (deliveries_one_live_trip_per_order): the second Ready's row is refused,
    its trip is cancelled at the company and the seller gets the usual "changed, refresh" (no 500)."""
    Deliveries.fail_create = ('Supabase error - create_delivery: duplicate key value violates unique constraint '
                              '"deliveries_one_live_trip_per_order"')
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 409 and len(seller.http.made("POST", "/orders/ord_1/cancel")) == 1


def test_t180_a12a_ready_records_the_trip_fee(seller):
    mark_ready()
    assert Deliveries.created[0]["trip_fee"] == 34800   # the AllinGo trip's fee.total, whole đồng


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
                      "driver_plate": None, "rebook_count": 2, "trip_fee": 34800,   # T180 A12: the new trip's fee
                      "allingo_partner": "grab"}   # T192 TC-10: the company of the new quote
    assert Orders.row["status"] == "ready"


def test_tc9_rebook_allingo_row_to_lalamove(seller, monkeypatch):
    monkeypatch.setattr(allingo_service, "enabled", lambda: False)
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_1", "status": "CANCELED", "rebook_count": 0}
    lalamove = SimpleNamespace(
        get_quotation=lambda **kw: SimpleNamespace(quotation_id="Q", stop_id_0="a", stop_id_1="b", total_fee=41000),
        place_order=lambda **kw: SimpleNamespace(status="ASSIGNING_DRIVER", lalamove_order_id="LM2", share_link="https://ll"))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: lalamove)
    rebook()
    [update] = Deliveries.updates
    assert (update["provider"], update["lalamove_order_id"], update["allingo_order_id"]) == ("lalamove", "LM2", None)
    assert update["allingo_partner"] is None   # T192 TC-11: the AllinGo company of the old trip is not kept


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
    code = "no_driver" if status == "delivery_failed" else "seller_reject_too_busy"   # a reason code (T178)
    sellers.update_seller_order_status(OID, Schema.RequestUpdateOrderStatus(status="cancelled", cancellation_reason=code),
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
def test_tc9_tc18_cancel_trip_goes_to_the_trip_company(seller, provider):
    # T180 A23: the buyer's DELETE endpoint is gone (test_t180_a23_buyer_trip_cancel_is_gone); cancel_trip, used by the
    # Ready rollback and the rebook, still cancels at the company that booked the trip
    cancelled = []
    trip = {"provider": provider, "allingo_order_id": "ord_1" if provider == "allingo" else None,
            "lalamove_order_id": None if provider == "allingo" else "LM1"}
    assert deliveries.cancel_trip(trip, lambda: SimpleNamespace(cancel_order=lambda i: cancelled.append(i) or True))
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
    ("delivering", "PICKED_UP"), ("delivered", "COMPLETED"),   # T191 TC-10: the test-mode lifecycle (test-mode.md)
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


# ── T191: AllinGo API fixes (docs/dev/20261111-allingo-api-fixes) ───────────

def test_t191_tc2_create_order_quotes_with_the_receiver_else_the_buyer(http, monkeypatch):
    fake_create_order(monkeypatch)
    monkeypatch.setattr(deliveries, "DAOUsers", lambda: SimpleNamespace(get_users=lambda uid: {"name": "Buyer", "phone": "0907654321"}))
    when = datetime.now(timezone.utc) + timedelta(days=2)
    for receiver, contact in [({"receiver_name": "Mẹ", "receiver_phone": "0912345678"}, ("Mẹ", "+84912345678")),
                              ({}, ("Buyer", "+84907654321"))]:
        orders.create_order(Schema.RequestCreateOrder(delivery_method="delivery", delivery_address="D7", delivery_lat=10.73,
                                                      delivery_lon=106.72, delivery_fee=34800, delivery_appointment=when,
                                                      **receiver), user={"id": "buyer"})
        body = http.made("POST", "/inquiries")[-1].json
        assert (body["dropoff"]["contact_name"], body["dropoff"]["contact_phone"]) == contact
        assert (body["pickup"]["contact_name"], body["pickup"]["contact_phone"]) == ("Bếp A", "+84901234567")


def test_t191_tc3_cart_quotation_without_a_buyer_phone(api, http, monkeypatch):
    cart_seller(monkeypatch, buyer_phone=None)
    r = post_quotation(api)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "quote_phone_missing"   # S1: the cart's own words
    assert http.made("POST", "/inquiries") == []


def test_t191_tc4_lalamove_quotation_needs_no_buyer_phone(api, monkeypatch):
    cart_seller(monkeypatch, buyer_phone=None)
    monkeypatch.setattr(deliveries, "DAOUsers", lambda: pytest.fail("Lalamove quotes without the buyer's profile"))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: SimpleNamespace(get_quotation=lambda **kw: SimpleNamespace(
        quotation_id="Q", stop_id_0="a", stop_id_1="b", total_fee=41000, currency="VND", distance_km=3)))
    assert post_quotation(api).json()["total_fee"] == 41000


def test_t191_tc5_tc7_booking_waits_between_tries(seller):
    seller.http.routes[("POST", "/orders")] = [reply(503, {"error": {"code": "partner_unavailable"}}), reply(201, trip())]
    mark_ready()
    assert seller.http.waits == [1] and Deliveries.created[0]["allingo_order_id"] == "ord_1"
    seller.http.routes[("POST", "/orders")] = reply(422, {"error": {"code": "validation_failed"}})   # TC-7
    seller.http.waits.clear()
    Orders.row["status"] = "confirmed"
    with pytest.raises(HTTPException):
        mark_ready()
    assert seller.http.waits == []


@pytest.mark.parametrize("header, wait", [({"Retry-After": "3"}, 3), ({"Retry-After": "120"}, 5), ({}, 1)])
def test_t191_tc6_429_waits_retry_after_at_most_5_s(seller, header, wait):
    seller.http.routes[("POST", "/orders")] = [reply(429, {"error": {"code": "rate_limited"}}, header), reply(201, trip())]
    mark_ready()
    assert seller.http.waits == [wait]


def test_t191_tc5_no_wait_after_the_last_try(seller):
    seller.http.routes[("POST", "/orders")] = reply(503, {"error": {"code": "partner_unavailable"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 3 and seller.http.waits == [1, 2]
    booking_failed(e)


@pytest.mark.parametrize("status", ["pending", "something_new", "draft", "queued", "on_going"])
def test_t191_tc8_a_trip_not_ended_is_taken(seller, status):
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip("ord_9", status, "queued")]})
    mark_ready()
    assert seller.http.made("POST", "/orders") == [] and Deliveries.created[0]["allingo_order_id"] == "ord_9"


@pytest.mark.parametrize("status", ["completed", "canceled", "return_finished"])
def test_t191_tc9_an_ended_trip_is_not_taken(seller, status):
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip("ord_9", status, "queued")]})
    mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 1 and Deliveries.created[0]["allingo_order_id"] == "ord_1"


def order_event(order_status, leg=None):
    body = event("x")
    body["data"]["object"] |= {"status": order_status, "delivery": leg}
    return body


def test_t191_tc10_delivered_finishes_the_order(hook):
    assert post_event(hook.client, event("delivered")).status_code == 200
    assert Deliveries.row["status"] == "COMPLETED" and Orders.row["status"] == "done" and hook.pushes == ["delivered"]


@pytest.mark.parametrize("leg", [None, {"track_link": "https://business.allingo.vn/track/ord_1"}])
def test_t191_tc11_no_delivery_status_reads_the_order_status(hook, leg):
    post_event(hook.client, order_event("queued", leg))
    assert Deliveries.row["status"] == "ASSIGNING_DRIVER" and Orders.writes == []   # anything else: kept
    post_event(hook.client, order_event("canceled", leg))
    assert Deliveries.row["status"] == "CANCELED" and Orders.row["status"] == "delivery_failed"
    assert [a[0] for a in hook.admin] == ["admin_delivery_failed"]
    Orders.row["status"], Deliveries.row["status"] = "ready", "ON_GOING"
    post_event(hook.client, order_event("completed", leg))
    assert Deliveries.row["status"] == "COMPLETED" and Orders.row["status"] == "done" and hook.pushes == ["delivered"]


def test_t191_tc11_return_finished_order_after_pickup_is_lost(hook):
    Deliveries.row["status"] = "PICKED_UP"
    post_event(hook.client, order_event("return_finished"))
    assert Deliveries.row["status"] == "LOST" and [a[0] for a in hook.admin] == ["admin_delivery_lost"]


def test_t191_tc12_cancel_retried_after_partner_cancel_failed(http):
    refused = reply(503, {"error": {"code": "partner_cancel_failed", "message": "The carrier refused the cancellation. Retry."}})
    http.routes[("POST", "/orders/ord_1/cancel")] = [refused, reply(200, {"id": "ord_1", "status": "canceled"})]
    assert allingo_service.get_allingo_service().cancel_order("ord_1") is True
    keys = [c.headers["Idempotency-Key"] for c in http.made("POST", "/orders/ord_1/cancel")]
    assert len(keys) == 2 and keys[0] != keys[1] and http.waits == [1]


def test_t191_tc13_cancel_gives_up_after_3_calls(http):
    http.routes[("POST", "/orders/ord_1/cancel")] = reply(503, {"error": {"code": "partner_cancel_failed"}})
    assert allingo_service.get_allingo_service().cancel_order("ord_1") is False
    assert len(http.made("POST", "/orders/ord_1/cancel")) == 3 and http.waits == [1, 2]


@pytest.mark.parametrize("profile, detail", [
    ({"address": "  "}, "Missing pickup or dropoff address. Please update your store address in settings."),
    ({"lat": None}, "Seller location not configured")])
def test_t191_tc14_rebook_checks_the_store_address(seller, monkeypatch, profile, detail):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    real = Orders.read_order_with_seller_coords
    monkeypatch.setattr(Orders, "read_order_with_seller_coords",
                        lambda self, oid: (lambda o: {**o, "seller_profiles": {**o["seller_profiles"], **profile}})(real(self, oid)))
    with pytest.raises(HTTPException) as e:
        rebook()
    assert (e.value.status_code, e.value.detail) == (400, detail)
    assert seller.http.calls == [] and Deliveries.updates == []


BLOCKED = ("admin_delivery_provider_blocked", f"/orders?open={OID}", {"code": OID[:8]})


@pytest.mark.parametrize("answer", [reply(403, {"error": {"code": "app_not_approved"}}), reply(403, {"error": {"code": "app_suspended"}}),
                                    reply(401, {"error": {"code": "token_revoked"}})])   # TC-16: 401 again after a new token
def test_t191_tc15_tc16_blocked_app_tells_the_admins_once(seller, answer):
    seller.http.routes[("POST", "/orders")] = answer
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert seller.admin == [BLOCKED] and seller.http.waits == []
    assert len(seller.http.made("POST", "/orders")) == (2 if answer.status_code == 401 else 1)
    booking_failed(e)


def test_t191_tc15_blocked_at_rebook_keeps_the_order(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    seller.http.routes[("POST", "/orders")] = reply(403, {"error": {"code": "app_suspended"}})
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 503 and Orders.row["status"] == "delivery_failed" and refunds == []
    assert seller.admin == [BLOCKED]


def test_t191_tc15_blocked_quote_at_ready_tells_the_admins(seller):
    seller.http.routes[("POST", "/inquiries")] = reply(403, {"error": {"code": "app_not_approved"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 502 and Orders.row["status"] == "confirmed" and seller.admin == [BLOCKED]


# ── T191 after QA (TC-20..43, S1-S7, Q1-Q4) ─────────────────────────────────

def test_t191_tc36_create_order_without_any_phone_is_400_not_502(http, monkeypatch):
    fake_create_order(monkeypatch)
    monkeypatch.setattr(deliveries, "DAOUsers", lambda: SimpleNamespace(get_users=lambda uid: {"name": "Buyer", "phone": None}))
    with pytest.raises(HTTPException) as e:
        orders.create_order(Schema.RequestCreateOrder(delivery_method="delivery", delivery_address="D7", delivery_lat=10.73,
                                                      delivery_lon=106.72, delivery_fee=34800,
                                                      delivery_appointment=datetime.now(timezone.utc) + timedelta(days=2)),
                            user={"id": "buyer"})
    assert (e.value.status_code, e.value.detail["code"]) == (400, "quote_phone_missing")


def test_t191_tc37_cart_uses_the_address_receiver(api, http, monkeypatch):
    cart_seller(monkeypatch, buyer_phone=None)
    r = api(deliveries.router).post("/deliveries/quotation", json={
        "seller_id": "s1", "delivery_lat": 10.73, "delivery_lon": 106.72, "delivery_address": "D7",
        "receiver_name": "Mẹ", "receiver_phone": "0912345678"})
    assert r.status_code == 200
    dropoff = http.made("POST", "/inquiries")[0].json["dropoff"]
    assert (dropoff["contact_name"], dropoff["contact_phone"]) == ("Mẹ", "+84912345678")


def test_t191_tc38_ready_keeps_buyer_phone_invalid(seller, monkeypatch):
    real = Orders.read_order_with_seller_coords
    monkeypatch.setattr(Orders, "read_order_with_seller_coords",
                        lambda self, oid: {**real(self, oid), "users": {"name": "Buyer", "phone": "12"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.detail["code"] == "buyer_phone_invalid" and seller.http.calls == []


def test_t191_tc39_tc43_cart_never_shows_the_store_settings_words_or_allingo_codes(api, http, monkeypatch):
    cart_seller(monkeypatch)
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_coords_by_id=lambda sid: {
        "lat": 10.77, "lon": 106.70, "address": "Q1", "store_name": "Bếp A", "phone": "123"}))
    r = post_quotation(api)   # TC-39: the store's phone is wrong
    assert (r.status_code, r.json()["detail"]) == (502, "Could not get a delivery fee quote. Please try again.")
    cart_seller(monkeypatch)
    http.routes[("POST", "/inquiries")] = reply(403, {"error": {"code": "app_not_approved"}})
    admin = []
    monkeypatch.setattr(push_service, "notify_admins", lambda *a, **f: admin.append(a))
    r = post_quotation(api)   # TC-43: refused account, no alert per cart (the wallet job tells)
    assert (r.status_code, r.json()["detail"]) == (502, "Could not get a delivery fee quote. Please try again.") and admin == []


@pytest.mark.parametrize("token", [reply(403, {"error": "unauthorized_client"}), reply(401, {"error": "invalid_client"})])
def test_t191_tc40_tc41_refused_token_at_ready(seller, token):
    seller.http.token_reply = token
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 502 and Orders.row["status"] == "confirmed" and refunds == []
    assert seller.admin == [BLOCKED]   # Q3: once, though the lookup failed first


def test_t191_tc42_refused_quote_at_rebook_keeps_the_order(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    seller.http.routes[("POST", "/inquiries")] = reply(403, {"error": {"code": "app_not_approved"}})
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 502 and Orders.row["status"] == "delivery_failed" and seller.admin == [BLOCKED]


def test_t191_tc20_timeout_then_a_pending_trip_without_delivery(seller):
    seller.http.routes[("POST", "/orders")] = requests.Timeout("read timeout")
    seller.http.routes[("GET", "/orders")] = [reply(200, {"data": []}), reply(200, {"data": [
        {"id": "ord_9", "status": "pending", "external_reference": OID, "fee": {"cod": 0, "total": 34800}, "delivery": None}]})]
    mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 1
    assert [(d["allingo_order_id"], d["status"]) for d in Deliveries.created] == [("ord_9", "ASSIGNING_DRIVER")]


def test_t191_tc21_lost_answer_and_failed_lookup_posts_again(seller):
    """Chosen: a failed lookup books again (a new key); the second trip, if any, is cancelled by its webhook (S7)."""
    seller.http.routes[("POST", "/orders")] = [requests.Timeout("read timeout"), reply(201, trip())]
    seller.http.routes[("GET", "/orders")] = [reply(200, {"data": []}), reply(503, {})]
    mark_ready()
    assert len(seller.http.made("POST", "/orders")) == 2


def test_t191_tc22_two_running_trips_take_one(seller):
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [trip("ord_a", "on_going", "courier_assigned"), trip("ord_b")]})
    mark_ready()
    assert seller.http.made("POST", "/orders") == [] and Deliveries.created[0]["allingo_order_id"] == "ord_a"


def test_t191_tc31_more_attempts_wait_1_2_4_then_the_deadline(seller, monkeypatch):
    monkeypatch.setattr(Settings, "get_positive_int", lambda self, key, default: 5 if key == "driver_booking_attempts" else default)
    seller.http.routes[("POST", "/orders")] = reply(503, {"error": {"code": "partner_unavailable"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    # Q4: a wait starts only if wait + 30 s still ends before 40 s: 1, 2, 4 (7 s); the 5 s wait would end at 42 s
    assert seller.http.waits == [1, 2, 4] and len(seller.http.made("POST", "/orders")) == 4
    booking_failed(e)


def test_t191_tc32_slow_calls_no_new_try_after_the_deadline(seller):
    seller.http.cost = 15   # every AllinGo call takes its whole timeout; the token is the first call's
    seller.http.routes[("POST", "/orders")] = reply(503, {"error": {"code": "partner_unavailable"}})
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert seller.http.waits == [] and len(seller.http.made("POST", "/orders")) == 1
    assert seller.http.now == 60   # token + lookup + quote + POST: the first try alone (not T191's), no second one
    booking_failed(e)


@pytest.mark.parametrize("answer, wait", [
    (reply(429, {}, {"Retry-After": "abc"}), 1), (reply(429, {}, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), 1),
    (reply(429, {}, {"Retry-After": "0"}), 1)])
def test_t191_tc33_odd_retry_after(seller, answer, wait):
    seller.http.routes[("POST", "/orders")] = [answer, reply(201, trip())]
    mark_ready()
    assert seller.http.waits == [wait]


def test_t191_tc34_rebook_tries_once(seller):
    Orders.row["status"] = "delivery_failed"
    Deliveries.row = {"id": "d1", "provider": "allingo", "allingo_order_id": "ord_0", "status": "CANCELED", "rebook_count": 0}
    seller.http.routes[("POST", "/orders")] = reply(503, {"error": {"code": "partner_unavailable"}})
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.status_code == 503 and seller.http.waits == [] and len(seller.http.made("POST", "/orders")) == 1


@pytest.mark.parametrize("late, calls, waits", [(0, 3, [1, 2]), (100, 1, [])])   # Q2: past the deadline, one call still
def test_t191_tc35_rollback_cancel_retries_in_time(seller, caplog, late, calls, waits):
    Deliveries.fail_create = True
    seller.http.routes[("POST", "/orders/ord_1/cancel")] = reply(503, {"error": {"code": "partner_cancel_failed"}})
    real = Deliveries.create_delivery

    def slow_insert(self, **kw):
        seller.http.now += late
        return real(self, **kw)
    Deliveries.create_delivery = slow_insert
    try:
        with pytest.raises(HTTPException) as e:
            mark_ready()
    finally:
        Deliveries.create_delivery = real
    assert e.value.status_code == 500 and seller.http.waits == waits
    assert len(seller.http.made("POST", "/orders/ord_1/cancel")) == calls and "MANUAL INTERVENTION" in caplog.text


def test_t191_tc24_tc25_late_or_repeated_events_after_delivered(hook):
    for _ in range(2):
        post_event(hook.client, event("delivered"))
    post_event(hook.client, event("delivering"))
    assert Deliveries.row["status"] == "COMPLETED" and Orders.row["status"] == "done" and hook.pushes == ["delivered"]


@pytest.mark.parametrize("order_status", ["return_finished", "canceled"])
def test_t191_tc26_failed_end_after_pickup_is_lost(hook, seller, order_status):
    Orders.row["status"] = "ready"
    Deliveries.row = {"id": "d1", "order_id": OID, "provider": "allingo", "allingo_order_id": "ord_1", "status": "PICKED_UP"}
    post_event(hook.client, order_event(order_status))
    assert Deliveries.row["status"] == "LOST" and Orders.row["status"] == "delivery_failed"
    with pytest.raises(HTTPException) as e:
        rebook()
    assert e.value.detail["code"] == "delivery_lost"


@pytest.mark.parametrize("leg", ["queued", "pending_schedule", "pickup_failed"])
def test_t191_tc27_cancelled_order_wins_over_a_delivery_not_ended(hook, leg):
    post_event(hook.client, order_event("canceled", {"status": leg}))
    assert Deliveries.row["status"] == "CANCELED" and Orders.row["status"] == "delivery_failed"
    assert [a[0] for a in hook.admin] == ["admin_delivery_failed"]


def test_t191_tc28_old_trip_after_a_rebook_changes_nothing(hook, http):
    Deliveries.row["allingo_order_id"] = "ord_new"
    for body in (order_event("canceled"), event("canceled", trip_id="ord_1")):
        body["data"]["object"]["id"] = "ord_1"
        assert post_event(hook.client, body).status_code == 200
    assert Deliveries.updates == [] and Orders.writes == [] and http.calls == []


def test_t191_tc29_completed_after_canceled_keeps_canceled(hook):
    Orders.row["status"], Deliveries.row["status"] = "delivery_failed", "CANCELED"
    post_event(hook.client, order_event("completed"))
    assert Deliveries.row["status"] == "CANCELED" and Orders.row["status"] == "delivery_failed"


# S7 + Q1: a second AllinGo trip for one order is cancelled when its webhook comes

def stray(hook, http, order_status="ready", row_status="ON_GOING", trip_status="queued", cancel=None):
    Orders.row["status"] = order_status
    Deliveries.row = {**Deliveries.row, "status": row_status}
    http.routes[("POST", "/orders/ord_2/cancel")] = cancel or reply(200, {"id": "ord_2", "status": "canceled"})
    body = event("courier_assigned", trip_id="ord_2")
    body["data"]["object"]["status"] = trip_status
    return post_event(hook.client, body)


@pytest.mark.parametrize("order_status, row_status", [("ready", "ON_GOING"), ("cancelled", "CANCELED"), ("done", "COMPLETED")])
def test_t191_s7_stray_trip_cancelled(hook, http, caplog, order_status, row_status):
    assert stray(hook, http, order_status, row_status).status_code == 200
    assert len(http.made("POST", "/orders/ord_2/cancel")) == 1 and "stray AllinGo trip" in caplog.text
    assert Deliveries.updates == [] and Orders.writes == []


def test_t191_s7_ended_stray_trip_or_a_rebook_booking_is_left_alone(hook, http):
    assert stray(hook, http, trip_status="canceled").status_code == 200
    assert stray(hook, http, "delivery_failed", "CANCELED").status_code == 503   # Q1: the rebook is writing its row
    assert http.made("POST", "/orders/ord_2/cancel") == []


def test_t191_s7_failed_cancel_answers_503(hook, http):
    assert stray(hook, http, cancel=reply(503, {"error": {"code": "partner_cancel_failed"}})).status_code == 503
    assert len(http.made("POST", "/orders/ord_2/cancel")) == 1 and http.waits == []   # AllinGo resends the event


def test_t191_g1_stray_trip_that_cannot_be_cancelled_is_done(hook, http):
    assert stray(hook, http, cancel=reply(409, {"error": {"code": "cannot_cancel"}})).status_code == 200   # no 44-hour resends
    assert len(http.made("POST", "/orders/ord_2/cancel")) == 1
    assert allingo_service.get_allingo_service().cancel_order("ord_2") is False   # Ready / rebook rollback: still a failure



# ── T192 C: the companies AllinGo may book (admin_settings allingo_partner_*) and deliveries.allingo_partner ─

def asked(http):
    return [c.json["filter_partner_ids"] for c in http.calls if c.path in ("/inquiries", "/orders") and c.method == "POST"]


def test_t192_tc6_tc8_cart_asks_the_companies_switched_on_now(api, http, monkeypatch):
    cart_seller(monkeypatch)
    SettingsRows.rows |= {"allingo_partner_gsm": 0}
    post_quotation(api)
    SettingsRows.rows |= {"allingo_partner_gsm": 1, "allingo_partner_lalamove": 1}   # TC-8: read on every quote
    post_quotation(api)
    assert asked(http) == [["grab"], ["grab", "gsm", "lalamove"]]


@pytest.mark.parametrize("env, want", [("simulator", ["simulator"]), (" grab , simulator ", ["grab", "simulator"]),
                                       ("", ["grab", "gsm"]), ("  ,  ", ["grab", "gsm"])])   # TC-18: empty = not set
def test_t192_tc7_tc18_env_wins_when_not_empty(http, monkeypatch, env, want):
    monkeypatch.setenv("ALLINGO_PARTNER_IDS", env)
    SettingsRows.rows |= {"allingo_partner_lalamove": 0}
    assert allingo_service.partner_ids() == want


@pytest.mark.parametrize("rows, want", [
    ({"allingo_partner_grab": 0, "allingo_partner_gsm": 1, "allingo_partner_lalamove": 0}, ["gsm"]),   # TC-16: 0 is off
    ({"allingo_partner_grab": 1, "allingo_partner_gsm": 0, "allingo_partner_lalamove": 1}, ["grab", "lalamove"]),
    ({}, ["grab", "gsm"]),                                                                                # TC-17: rows missing
    ({"allingo_partner_grab": 2, "allingo_partner_gsm": "abc", "allingo_partner_lalamove": True}, ["grab", "gsm"]),
    ("down", ["grab", "gsm"])])                                                                           # TC-17: read error
def test_t192_tc16_tc17_switch_values(http, caplog, rows, want):
    SettingsRows.rows = rows
    assert allingo_service.partner_ids() == want
    if rows in ({}, "down"):
        assert "using" in caplog.text   # logged, never a 500


def test_t192_tc19_quote_of_a_company_not_asked_is_dropped(seller):
    seller.http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [quote(20000, "cheap_lalamove", partner="lalamove"),
                                                                        quote(34800, partner="gsm")]})
    mark_ready()
    [post] = seller.http.made("POST", "/orders")
    assert post.json["service_id"] == "svc34800" and Deliveries.created[0]["allingo_partner"] == "gsm"   # TC-9


def test_t192_tc20_the_trip_asks_only_the_quoted_company(seller):
    seller.http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [quote(30000, partner="gsm"), quote(34800)]})
    mark_ready()
    assert asked(seller.http) == [["grab", "gsm"], ["gsm"]]   # POST /orders: the cheapest quote's company only


def test_t192_tc21_no_company_on(api, seller, monkeypatch):
    SettingsRows.rows = {"allingo_partner_grab": 0, "allingo_partner_gsm": 0, "allingo_partner_lalamove": 0}
    cart_seller(monkeypatch)
    r = post_quotation(api)
    assert (r.status_code, r.json()["detail"]) == (502, "Could not get a delivery fee quote. Please try again.")
    with pytest.raises(HTTPException) as e:
        mark_ready()
    assert e.value.status_code == 502 and Orders.row["status"] == "confirmed" and refunds == []
    assert seller.http.calls == [c for c in seller.http.calls if c.path == "/orders" and c.method == "GET"]   # no /inquiries


@pytest.mark.parametrize("leg, partner", [({"status": "courier_assigned", "partner": {"id": "grab", "name": "Grab"}}, "grab"),
                                          (None, None)])
def test_t192_tc22_taken_trip_keeps_its_own_company(seller, leg, partner):
    seller.http.routes[("GET", "/orders")] = reply(200, {"data": [{**trip("ord_9", "on_going"), "delivery": leg}]})
    seller.http.routes[("POST", "/inquiries")] = reply(200, {"quotes": [quote(30000, partner="gsm")]})
    mark_ready()
    assert seller.http.made("POST", "/orders") == [] and Deliveries.created[0]["allingo_partner"] == partner


def test_t192_tc11_lalamove_ready_has_no_allingo_company(seller, monkeypatch):
    monkeypatch.setattr(allingo_service, "enabled", lambda: False)
    lalamove = SimpleNamespace(
        get_quotation=lambda **kw: SimpleNamespace(quotation_id="Q", stop_id_0="a", stop_id_1="b", total_fee=41000),
        place_order=lambda **kw: SimpleNamespace(status="ASSIGNING_DRIVER", lalamove_order_id="LM2", share_link="https://ll"))
    monkeypatch.setattr("services.lalamove_service.get_lalamove_service", lambda: lalamove)   # Ready imports it locally
    mark_ready()
    assert Deliveries.created[0].get("allingo_partner") is None and Deliveries.created[0]["lalamove_order_id"] == "LM2"
