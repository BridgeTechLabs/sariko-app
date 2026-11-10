"""Regression baseline R1 (docs/dev/regression-baseline): /cart, GET /orders and /deliveries routes no other
test reached, plus the harder Lalamove webhook cases (wrong key, missing secret, the same event twice,
broken JSON). Status code and JSON shape as served today. DAOs and Lalamove are faked.

Run from tests/backend:  pytest integration/test_api_baseline_cart_orders_deliveries.py
"""
from types import SimpleNamespace

import pytest

from apis import cart, deliveries, orders
from test_deliveries_webhook import _FakeDeliveryDAO, _FakeOrderDAO, _make_webhook_body

VALIDATION = {"detail", "errors"}


# ── /cart ───────────────────────────────────────────────────────────────────

@pytest.fixture
def carts(monkeypatch):
    """DAOCarts + DAOCartItems fakes; .cart = the buyer's cart row (None = no cart)."""
    class Carts:
        cart = {"id": "cart1", "seller_id": "s1", "seller_profiles": {"store_name": "Bếp A"}}
        log = []

        def read_cart_by_user_id_seller_id(self, user_id):
            return Carts.cart

        def delete_cart(self, cart_id):
            Carts.log.append(("delete_cart", cart_id))

    class Items:
        def update_quantity(self, **kw):
            Carts.log.append(("update_quantity", kw))

        def remove_item(self, **kw):
            Carts.log.append(("remove_item", kw))

    Carts.log = []
    monkeypatch.setattr(cart, "DAOCarts", Carts)
    monkeypatch.setattr(cart, "DAOCartItems", Items)
    monkeypatch.setattr(orders, "DAOAdminConfig", lambda: SimpleNamespace(get_positive_int=lambda key, default: default))
    return Carts


def test_cart_update_quantity(api, carts):
    r = api(cart.router).patch("/cart/update", json={"food_item_id": "f1", "quantity": 3, "variant_id": "v1"})
    assert r.json() == {"success": True}
    assert carts.log == [("update_quantity", {"cart_id": "cart1", "food_item_id": "f1", "quantity": 3, "variant_id": "v1"})]


def test_cart_update_quantity_must_be_positive(api, carts):
    r = api(cart.router).patch("/cart/update", json={"food_item_id": "f1", "quantity": 0})
    assert r.status_code == 422 and set(r.json()) == VALIDATION and carts.log == []


def test_cart_remove_and_clear(api, carts):
    c = api(cart.router)
    assert c.delete("/cart/remove/f1", params={"variant_id": "v1"}).json() == {"success": True}
    assert c.delete("/cart/clear").json() == {"success": True}
    assert carts.log == [("remove_item", {"cart_id": "cart1", "food_item_id": "f1", "variant_id": "v1"}),
                         ("delete_cart", "cart1")]


@pytest.mark.parametrize("method,path,body", [("patch", "/cart/update", {"food_item_id": "f1", "quantity": 1}),
                                              ("delete", "/cart/remove/f1", None), ("delete", "/cart/clear", None)])
def test_cart_without_a_cart_is_404(api, carts, method, path, body):
    carts.cart = None
    r = api(cart.router).request(method.upper(), path, json=body)
    assert r.status_code == 404 and r.json() == {"detail": "Cart not found"} and carts.log == []


@pytest.mark.parametrize("variants,variant_id,detail", [
    ([], "v1", "This dish has no price options"),
    ([{"id": "v1", "is_available": True}], None, "Please choose a price option"),
    ([{"id": "v1", "is_available": True}], "v-other", "Invalid price option for this dish"),
    ([{"id": "v1", "is_available": False}], "v1", "This price option is sold out"),
])
def test_cart_add_price_option_rules(api, monkeypatch, carts, variants, variant_id, detail):
    """Money: a dish with price options never enters the cart priced from food_items.price."""
    class Variants:
        def read_by_food_item_id(self, food_item_id):
            return variants

    monkeypatch.setattr(cart, "DAOFoodItemVariants", Variants)
    r = api(cart.router).post("/cart/add", json={"seller_id": "s1", "food_item_id": "f1", "variant_id": variant_id})
    assert r.status_code == 400 and r.json() == {"detail": detail} and carts.log == []


def test_cart_add_from_another_seller(api, monkeypatch, carts):
    monkeypatch.setattr(cart, "DAOFoodItemVariants", lambda: SimpleNamespace(read_by_food_item_id=lambda f: []))
    monkeypatch.setattr(cart, "DAOFoodItems", lambda: SimpleNamespace(read_order_gate=lambda f: None))
    r = api(cart.router).post("/cart/add", json={"seller_id": "s2", "food_item_id": "f1"})
    assert r.status_code == 400
    assert r.json() == {"detail": {"message": "Cart contains items from another seller", "current_seller_name": "Bếp A"}}


# ── GET /orders ─────────────────────────────────────────────────────────────

def test_orders_list_is_the_buyers(api, monkeypatch):
    seen = []
    monkeypatch.setattr(orders, "DAOOrders", lambda: SimpleNamespace(
        read_orders_by_user_id=lambda user_id: seen.append(user_id) or [{"id": "o1"}]))
    assert api(orders.router).get("/orders").json() == {"success": True, "orders": [{"id": "o1"}]} and seen == ["u1"]


# ── /deliveries ─────────────────────────────────────────────────────────────

class Lalamove:
    cancelled, cancel_ok = [], True

    def get_quotation(self, **kw):
        Lalamove.quoted = kw
        return SimpleNamespace(quotation_id="Q1", stop_id_0="A", stop_id_1="B", total_fee=32000, currency="VND", distance_km=4.2)

    def cancel_order(self, lalamove_order_id):
        Lalamove.cancelled.append(lalamove_order_id)
        return Lalamove.cancel_ok


@pytest.fixture
def lalamove(monkeypatch):
    Lalamove.cancelled, Lalamove.cancel_ok = [], True
    monkeypatch.setattr(deliveries, "get_lalamove_service", Lalamove)
    return Lalamove


@pytest.mark.parametrize("coords,status,body", [
    ({"lat": 10.77, "lon": 106.7, "address": "1 Lê Lợi"}, 200,
     {"success": True, "quotation_id": "Q1", "stop_id_0": "A", "stop_id_1": "B", "total_fee": 32000, "currency": "VND", "distance_km": 4.2}),
    (None, 404, {"detail": "Seller not found"}),
    ({"lat": None, "lon": None}, 400, {"detail": "Seller location not configured"}),
])
def test_deliveries_quotation(api, monkeypatch, lalamove, coords, status, body):
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_coords_by_id=lambda sid: coords))
    r = api(deliveries.router).post("/deliveries/quotation",
                                    json={"seller_id": "s1", "delivery_lat": 10.8, "delivery_lon": 106.6, "delivery_address": "2 Hai Bà Trưng"})
    assert (r.status_code, r.json()) == (status, body)


def test_deliveries_quotation_lalamove_down_is_500(api, monkeypatch):
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_coords_by_id=lambda sid: {"lat": 1, "lon": 1}))
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: SimpleNamespace(get_quotation=lambda **kw: 1 / 0))
    r = api(deliveries.router).post("/deliveries/quotation", json={"seller_id": "s1", "delivery_lat": 1, "delivery_lon": 1, "delivery_address": "x"})
    assert r.status_code == 500 and set(r.json()) == {"detail"}


def test_deliveries_quotation_needs_coordinates(api):
    r = api(deliveries.router).post("/deliveries/quotation", json={"seller_id": "s1", "delivery_address": "x"})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


DELIVERY = {"id": "d1", "order_id": "o1", "lalamove_order_id": "LM1", "status": "ASSIGNING_DRIVER", "driver_name": "Tài",
            "driver_phone": "+84900000000", "driver_plate": "59A", "tracking_url": None, "share_link": "https://share", "rebook_count": 1}


@pytest.fixture
def delivery_rows(monkeypatch):
    """.order (buyer / seller read) and .delivery rows; .updates = DAODeliveries.update_delivery calls."""
    class Rows:
        order, delivery, updates, profile = {"id": "o1"}, dict(DELIVERY), [], {"id": "s1"}

    class Deliveries:
        def read_delivery_by_order_id(self, order_id):
            return Rows.delivery

        def update_delivery(self, delivery_id, data):
            Rows.updates.append((delivery_id, data))

    Rows.updates = []
    monkeypatch.setattr(deliveries, "DAODeliveries", Deliveries)
    monkeypatch.setattr(deliveries, "DAOOrders", lambda: SimpleNamespace(read_order_by_id=lambda oid, uid: Rows.order,
                                                                         read_order_by_id_for_seller=lambda oid, sid: Rows.order,
                                                                         read_delivery_history=lambda oid: Rows.history,
                                                                         touch_order=lambda oid: None))
    Rows.history = [{"status": "ON_GOING", "changed_at": "2026-11-10T03:00:00+00:00"},   # a driver turned it down at 03:05
                    {"status": "ASSIGNING_DRIVER", "changed_at": "2026-11-10T03:05:00+00:00"},
                    {"status": "ASSIGNING_DRIVER", "changed_at": "2026-11-10T03:06:00+00:00"}]   # same status: clock keeps 03:05
    monkeypatch.setattr(deliveries, "DAOAdminConfig", lambda: SimpleNamespace(get_positive_int=lambda key, default: 20))
    monkeypatch.setattr(deliveries, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_profile_by_user_id=lambda uid: Rows.profile))
    monkeypatch.setattr(deliveries, "rebook_max", lambda: 3)
    return Rows


def test_deliveries_buyer_status(api, delivery_rows):
    r = api(deliveries.router).get("/deliveries/o1/status")
    assert r.json() == {"success": True, "delivery": {k: DELIVERY[k] for k in
                        ("status", "driver_name", "driver_phone", "driver_plate", "tracking_url", "share_link")}}
    delivery_rows.delivery = None
    assert api(deliveries.router).get("/deliveries/o1/status").json() == {"success": True, "delivery": None}


def test_deliveries_seller_status(api, delivery_rows):
    d = api(deliveries.router).get("/deliveries/o1/seller-status").json()["delivery"]
    assert d == {k: DELIVERY[k] for k in ("status", "driver_name", "driver_phone", "driver_plate", "share_link", "rebook_count")} | {
        "rebook_max": 3, "stuck_minutes": 20, "status_since": "2026-11-10T03:05:00+00:00"}   # T180 A36


@pytest.mark.parametrize("path,who,status,detail", [
    ("/deliveries/o1/status", "order", 404, "Order not found"),            # not the buyer's order
    ("/deliveries/o1/seller-status", "order", 404, "Order not found"),     # not this seller's order
    ("/deliveries/o1/seller-status", "profile", 403, "Not a seller"),
])
def test_deliveries_status_errors(api, delivery_rows, path, who, status, detail):
    setattr(delivery_rows, who, None)
    r = api(deliveries.router).get(path)
    assert r.status_code == status and r.json() == {"detail": detail}


def test_t180_a23_buyer_trip_cancel_is_gone(api, delivery_rows, lalamove):
    """The buyer's DELETE /deliveries/{id}/cancel was removed (no screen called it, it left the order ready, T180 A23)."""
    assert api(deliveries.router).delete("/deliveries/o1/cancel").status_code in (404, 405)
    assert lalamove.cancelled == [] and delivery_rows.updates == []


# ── Lalamove webhook: the harder cases ──────────────────────────────────────

def _webhook(fastapi_client, raw):
    return fastapi_client.post("/deliveries/webhook", content=raw, headers={"Content-Type": "application/json"})


@pytest.fixture
def hook(monkeypatch):
    fake_del = _FakeDeliveryDAO({"id": "d1", "order_id": "o1", "lalamove_order_id": "LM1", "status": "PICKED_UP"})
    fake_ord = _FakeOrderDAO({"id": "o1", "status": "ready"})
    monkeypatch.setattr(deliveries, "DAODeliveries", lambda: fake_del)
    monkeypatch.setattr(deliveries, "DAOOrders", lambda: fake_ord)
    delivered = []
    monkeypatch.setattr(deliveries.push_service, "notify_seller_delivered", delivered.append)
    return SimpleNamespace(delivery=fake_del, order=fake_ord, delivered=delivered)


def test_webhook_wrong_api_key_is_401(fastapi_client, lalamove_secret, hook):
    _, raw = _make_webhook_body("not-our-key", lalamove_secret, "ORDER_STATUS_CHANGED", {"order": {"orderId": "LM1", "status": "COMPLETED"}})
    r = _webhook(fastapi_client, raw)
    assert r.status_code == 401 and r.json() == {"detail": "Invalid apiKey"} and hook.delivery.last_update is None


def test_webhook_without_our_secret_is_503(fastapi_client, lalamove_secret, lalamove_api_key, hook, monkeypatch):
    monkeypatch.setenv("LALAMOVE_API_SECRET", "")
    _, raw = _make_webhook_body(lalamove_api_key, lalamove_secret, "ORDER_STATUS_CHANGED", {"order": {"orderId": "LM1", "status": "COMPLETED"}})
    r = _webhook(fastapi_client, raw)
    assert r.status_code == 503 and r.json() == {"detail": "Webhook not configured"} and hook.order.last_status is None


def test_webhook_signed_by_another_secret_is_401(fastapi_client, lalamove_api_key, hook):
    _, raw = _make_webhook_body(lalamove_api_key, "other-secret", "ORDER_STATUS_CHANGED", {"order": {"orderId": "LM1", "status": "COMPLETED"}})
    r = _webhook(fastapi_client, raw)
    assert r.status_code == 401 and r.json() == {"detail": "Invalid signature"} and hook.order.last_status is None


def test_webhook_same_completed_event_twice(fastapi_client, lalamove_secret, lalamove_api_key, hook):
    """Lalamove retries: both calls answer 200 and the order stays done. The order moves (and the seller
    is pushed) once: a done order is not moved again (T161 QD 7)."""
    _, raw = _make_webhook_body(lalamove_api_key, lalamove_secret, "ORDER_STATUS_CHANGED", {"order": {"orderId": "LM1", "status": "COMPLETED"}})
    assert [_webhook(fastapi_client, raw).json() for _ in range(2)] == [{"success": True}] * 2
    assert hook.order.last_status == "done" and hook.order._order["status"] == "done" and len(hook.delivered) == 1


def test_webhook_broken_json_answers_200_not_ok(fastapi_client, hook):
    r = _webhook(fastapi_client, b"{not json")
    assert r.status_code == 200 and r.json() == {"success": False, "detail": "Internal error"}   # no retry storm


# ── T180 A27: Lalamove statuses never step back, except a driver turning the trip down (docs/dev/20261110-delivery-tech) ──

def _send(fastapi_client, key, secret, status, event="ORDER_STATUS_CHANGED", driver=None):
    data = {"order": {"orderId": "LM1", "status": status}} | ({"driver": driver} if driver else {})
    return _webhook(fastapi_client, _make_webhook_body(key, secret, event, data)[1]).json()


@pytest.mark.parametrize("current, late", [("PICKED_UP", "ON_GOING"), ("COMPLETED", "ON_GOING"), ("COMPLETED", "PICKED_UP"),
                                           ("COMPLETED", "ASSIGNING_DRIVER"), ("CANCELED", "ASSIGNING_DRIVER"),
                                           ("EXPIRED", "COMPLETED")])
def test_t180_a27a_late_events_change_nothing(fastapi_client, lalamove_secret, lalamove_api_key, hook, current, late):
    hook.delivery._delivery["status"] = current
    assert _send(fastapi_client, lalamove_api_key, lalamove_secret, late) == {"success": True}
    assert hook.delivery.last_update is None and hook.delivery._delivery["status"] == current


def test_t180_a27a_forward_and_resent(fastapi_client, lalamove_secret, lalamove_api_key, hook):
    hook.delivery._delivery["status"] = "ON_GOING"
    _send(fastapi_client, lalamove_api_key, lalamove_secret, "PICKED_UP")
    assert hook.delivery._delivery["status"] == "PICKED_UP"
    _send(fastapi_client, lalamove_api_key, lalamove_secret, "PICKED_UP")   # resent: same status, no harm
    assert hook.delivery._delivery["status"] == "PICKED_UP"


@pytest.mark.parametrize("current", ["ON_GOING", "PICKED_UP"])
def test_t180_a27b_driver_turns_it_down(fastapi_client, lalamove_secret, lalamove_api_key, hook, current):
    """Lalamove v3 Driver Rejection: ON_GOING / PICKED_UP -> ASSIGNING_DRIVER, another driver is matched."""
    hook.delivery._delivery.update(status=current, driver_name="Old", driver_phone="+84900000001", driver_plate="59A",
                                   share_link="https://share")
    _send(fastapi_client, lalamove_api_key, lalamove_secret, "ASSIGNING_DRIVER")
    row = hook.delivery._delivery
    assert (row["status"], row["driver_name"], row["driver_phone"], row["driver_plate"]) == ("ASSIGNING_DRIVER", None, None, None)
    assert row["share_link"] == "https://share" and hook.order._order["status"] == "ready"   # same trip, order unchanged
    _send(fastapi_client, lalamove_api_key, lalamove_secret, "ON_GOING", "DRIVER_ASSIGNED", {"name": "New", "phone": "+84900000002"})
    assert (row["status"], row["driver_name"]) == ("ON_GOING", "New")
