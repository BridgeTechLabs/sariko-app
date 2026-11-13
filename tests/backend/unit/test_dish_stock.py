"""Seller-menu đợt 2 S1, dish stock (ADR 0004, README luồng 20261112-seller-menu QĐ2-*): the paid path takes the stock
and cancels + refunds an order a dish was short for, and pushes the seller for a dish that just went below its minimum
(TC2-20, TC2-21, TC2-37); the early checks at cart add, order create and pay link (TC2-14..19, TC2-41, TC2-43..45);
the seller PATCH (TC2-22, TC2-31); reads carry sold_out without an RPC (TC2-23, TC2-42). Was test_daily_portions.py.
The SQL (reserve / trigger / migration) is tests/sql/g5_portions.sql on DEV."""
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import apis.orders as orders
from apis import cart, sellers
from core.auth import verify_token
from dao.dao_food_items import DAOFoodItems
from dao.dao_orders import DAOOrders
from dao.dao_refunds import DAORefunds
from schemas import Schema
from services import push_service
from utils.stock import add_sold_out, stock_sold_out
from test_order_delivery_fee import created, fakes  # noqa: F401  (autouse fixture: fake DAOs for POST /orders)
from test_payment_reconcile import FakeOrders, OID, answer, client as pay_client, env  # noqa: F401  (fixtures)

ORDER_ID = "abc12345-678a-4bcd-9012-345678901234"
FRIED = {"id": "food-9", "name": "Fried chicken", "stock": 0, "min_quantity": 1}


def make_ipn_params(secret, order_id, amount_vnd):
    """A signed paid IPN (same signing as integration/test_payments_ipn.py)."""
    from apis.payments import _hmac_sha512
    params = {"vnp_Amount": str(amount_vnd * 100), "vnp_PayDate": "20260430120500", "vnp_ResponseCode": "00",
              "vnp_TmnCode": "TEST_TMN", "vnp_TransactionNo": "14567890", "vnp_TransactionStatus": "00",
              "vnp_TxnRef": f"{order_id.replace('-', '')}_20260430120000"}
    data = "&".join(f"{urllib.parse.quote_plus(k, safe='')}={urllib.parse.quote_plus(v, safe='')}" for k, v in sorted(params.items()))
    return params | {"vnp_SecureHash": _hmac_sha512(secret, data)}


# ─── IPN paid: reserve_order_stock ────────────────────────────────────────────
class _Result:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class _Query:
    """orders table: a read returns the row, an update applies when every eq() filter matches."""

    def __init__(self, client):
        self.client, self.payload, self.filters = client, None, {}

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def select(self, *args):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        row = self.client.order
        if self.payload is None:
            return _Result(dict(row))
        if any(row.get(k) != v for k, v in self.filters.items()):
            return _Result([])
        self.client.calls.append(("update", *self.payload))
        row.update(self.payload)
        return _Result([dict(row)])


class _Client:
    """reserve = what reserve_order_stock answers: None (a dish short), [] or the dishes that crossed."""

    def __init__(self, reserve):
        self.reserve, self.calls = reserve, []
        self.order = {"id": ORDER_ID, "user_id": "buyer", "seller_user_id": "seller", "status": "pending",
                      "payment_status": "pending", "total_amount": "100000", "transaction_ref": None,
                      "ipn_data": None, "payment_create_date": "20260430120000"}

    def rpc(self, name, params):
        self.calls.append(("rpc", name, params))
        if name == "reserve_order_stock":
            return _Result(self.reserve)
        if name == "update_order_payment_status":
            self.order.update(payment_status=params["p_status"], transaction_ref=params["p_transaction_ref"])
        return _Result(None)

    def table(self, name):
        return _Query(self)


@pytest.fixture
def ipn(fastapi_client, vnp_secret, monkeypatch):
    """A paid IPN through apply_vnpay_result and the real DAOOrders on a fake client."""
    def call(reserve, stock_push_fails=False, new_order_push_fails=False):
        client = _Client(reserve)
        dao = DAOOrders.__new__(DAOOrders)
        dao._table_name, dao._supabase_client = "orders", client
        monkeypatch.setattr(dao, "_invalidate_cache_for_order", lambda order_id: None, raising=False)
        monkeypatch.setattr("dao.dao_orders._invalidate_seller_orders", lambda seller_id: None)
        monkeypatch.setattr("apis.payments.DAOOrders", lambda: dao)
        monkeypatch.setattr("apis.payments.DAOPayments", lambda: type("P", (), {"create_payment": lambda self, **kw: None})())
        monkeypatch.setattr("dao.dao_orders.DAOAdminConfig", lambda: type("C", (), {
            "get_positive_int": lambda self, key, default: default, "get_int_in_range": lambda self, *a: 0})())
        pushes, refunds = [], []
        def new_order(order):
            if new_order_push_fails:
                raise RuntimeError("new-order push down")
            pushes.append("new_order")
        monkeypatch.setattr("dao.dao_orders.push_service.notify_new_order", new_order)
        monkeypatch.setattr("dao.dao_orders.push_service.notify_order_status", lambda order: pushes.append(order["status"]))

        def stock_push(seller_user_id, dish):
            if stock_push_fails:
                raise RuntimeError("push lookup down")
            pushes.append(("stock", seller_user_id, dish["name"]))
        monkeypatch.setattr("dao.dao_orders.push_service.notify_seller_stock", stock_push)
        monkeypatch.setattr(DAORefunds, "__init__", lambda self: None)
        monkeypatch.setattr(DAORefunds, "create_refund", lambda self, **kw: refunds.append(kw))
        params = make_ipn_params(vnp_secret, ORDER_ID, 100000)
        res = fastapi_client.get("/payments/vnpay/ipn", params=params)
        return res.json(), client, pushes, refunds, params
    return call


def test_tc2_21_short_while_paying(ipn):
    body, client, pushes, refunds, params = ipn(reserve=None)
    assert body["RspCode"] == "00"
    order = client.order
    assert (order["status"], order["cancellation_reason"], order["payment_status"]) == ("cancelled", "sold_out", "paid")
    [refund] = refunds
    assert (refund["order_id"], refund["amount"], refund["reason"]) == (ORDER_ID, Decimal("100000"), "sold_out")
    assert refund["original_txn_ref"] == params["vnp_TxnRef"]
    assert refund["ipn_data"]["vnp_TransactionNo"] == params["vnp_TransactionNo"]   # saved before the cancel
    assert pushes == ["cancelled"]                       # buyer told; no new-order and no out-of-stock push
    names = [c[1] for c in client.calls if c[0] == "rpc"]
    assert "compute_order_withholding" not in names
    assert names.index("reserve_order_stock") < names.index("update_order_payment_status")


def test_tc2_37_nothing_crossed_is_a_normal_payment(ipn):
    body, client, pushes, refunds, _ = ipn(reserve=[])   # [] is falsy but not "short"
    assert body["RspCode"] == "00"
    assert (client.order["status"], client.order["payment_status"]) == ("pending", "paid")
    assert pushes == ["new_order"] and refunds == []
    assert any(c[1] == "compute_order_withholding" for c in client.calls)
    [reserve] = [c[2] for c in client.calls if c[1] == "reserve_order_stock"]
    assert reserve == {"p_order_id": ORDER_ID, "p_cooldown_minutes": 30}   # admin_settings stock_alert_cooldown_minutes default


def test_tc2_20_seller_pushed_once_per_dish(ipn):
    body, client, pushes, _, _ = ipn(reserve=[FRIED])
    assert body["RspCode"] == "00" and client.order["payment_status"] == "paid"
    assert pushes == ["new_order", ("stock", "seller", "Fried chicken")]


def test_tc2_20_push_failure_keeps_the_ipn(ipn):
    body, client, pushes, refunds, _ = ipn(reserve=[FRIED], stock_push_fails=True)
    assert body["RspCode"] == "00" and client.order["payment_status"] == "paid" and refunds == []


def test_g1_new_order_push_failure_keeps_the_stock_push(ipn):
    body, client, pushes, _, _ = ipn(reserve=[FRIED], new_order_push_fails=True)
    assert body["RspCode"] == "00" and pushes == [("stock", "seller", "Fried chicken")]


def test_stock_push_texts(monkeypatch):
    sent = []
    monkeypatch.setattr(push_service, "_send_async", lambda user, event, url, **f: sent.append((user, event, url, f)))
    push_service.notify_seller_stock("seller", FRIED)
    push_service.notify_seller_stock("seller", {"name": "x" * 70, "stock": 2, "min_quantity": 3})
    assert sent[0] == ("seller", "seller_stock_out", "/seller/menu", {"dish": "Fried chicken", "n": 0, "m": 1})
    assert sent[1][1] == "seller_stock_low" and len(sent[1][3]["dish"]) == 60
    assert push_service._message("seller_stock_low", "vi", sent[1][3])[1] == \
        f"{'x' * 60} còn 2 phần, ít hơn mức tối thiểu 3 phần mỗi đơn. Người mua đang thấy hết hàng."
    assert push_service._message("seller_stock_out", "en", sent[0][3])[1] == "Fried chicken is sold out. Enter new stock to keep selling."


# ─── Sold out = stock below the minimum per order (QĐ2-7) ─────────────────────
@pytest.mark.parametrize("food, want", [
    ({"stock": None, "min_quantity": 3}, False),   # no limit
    ({"stock": 0, "min_quantity": 1}, True),
    ({"stock": 2, "min_quantity": 3}, True),
    ({"stock": 3, "min_quantity": 3}, False),
    ({"stock": 0, "min_quantity": None}, True),    # TC2-44: null minimum counts as 1
    ({"stock": 1}, False),
])
def test_sold_out(food, want):
    assert stock_sold_out(food) is want


# ─── POST /orders (QĐ2-8 b, QĐ2-9, QĐ2-12) ─────────────────────────────────────
def _cart(rows, stock=None, min_quantity=1, preorder_day=0):
    """rows = quantities of one dish over several cart rows (other options / levels)."""
    return {"id": "cart", "seller_id": "seller", "cart_items": [
        {"id": f"row-{n}", "quantity": q, "food_items": {
            "id": "food-1", "seller_id": "seller", "name": "Adobo", "price": 50000, "is_available": True,
            "preorder_day": preorder_day, "stock": stock, "min_quantity": min_quantity},
         "food_item_variants": None} for n, q in enumerate(rows)]}


def _order(monkeypatch, cart_row, appointment=None):
    monkeypatch.setattr(orders, "DAOCartItems", lambda: type("C", (), {"read_cart_items_by_user_id": lambda self, user_id: cart_row})())
    return orders.create_order(Schema.RequestCreateOrder(delivery_method="pickup", delivery_appointment=appointment),
                               user={"id": "buyer"})


def test_tc2_43_order_sums_the_rows_of_a_dish(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _order(monkeypatch, _cart([2, 3], stock=3))
    assert e.value.status_code == 409 and created == []
    assert e.value.detail == {"code": "portions_left", "message": "Only 3 portion(s) left: Adobo", "name": "Adobo", "remaining": 3}


def test_order_sold_out_dish_refused_as_no_longer_available(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _order(monkeypatch, _cart([1], stock=0))
    assert e.value.status_code == 400 and e.value.detail["code"] == "no_longer_available" and created == []


def test_tc2_17_under_the_minimum(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _order(monkeypatch, _cart([1], min_quantity=2))
    assert e.value.status_code == 400 and created == []
    assert e.value.detail == {"code": "min_quantity", "message": "At least 2 of Adobo in one order", "name": "Adobo", "min": 2}


def test_tc2_16_minimum_over_two_rows(monkeypatch):
    res = _order(monkeypatch, _cart([1, 1], stock=5, min_quantity=2))   # 1 Coca + 1 Pepsi
    assert res["success"] and len(created) == 1


def test_tc2_15_preorder_uses_the_same_stock(monkeypatch):
    res = _order(monkeypatch, _cart([1], stock=1, preorder_day=2), appointment=datetime.now(timezone.utc) + timedelta(days=3))
    assert res["success"] and len(created) == 1


def test_tc2_44_null_minimum(monkeypatch):
    res = _order(monkeypatch, _cart([1], stock=4, min_quantity=None))
    assert res["success"] and len(created) == 1


# ─── POST /cart/add (QĐ2-8 a) ─────────────────────────────────────────────────
@pytest.fixture
def add_to_cart(monkeypatch):
    app = FastAPI()
    app.include_router(cart.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    monkeypatch.setattr("apis.cart._validate_variant", lambda *a: None)
    added = []
    monkeypatch.setattr("apis.cart.DAOCarts", lambda: type("Ca", (), {
        "read_cart_by_user_id_seller_id": lambda self, user_id: {"id": "cart", "seller_id": "seller-1"}})())

    def call(quantity, stock, in_cart=2, min_quantity=1, preorder_day=0):
        monkeypatch.setattr("apis.cart.DAOCartItems", lambda: type("CI", (), {
            "read_cart_items_by_user_id": lambda self, user_id: _cart([in_cart] if in_cart else []),
            "add_item": lambda self, cart_id, food_item_id, variant_id, option_ids, q, *caps: added.append(q)})())
        gate = {"seller_id": "seller-1", "name": "Adobo", "is_available": True, "preorder_day": preorder_day,
                "stock": stock, "min_quantity": min_quantity,
                "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70, "is_open": True}}
        monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("G", (), {"read_order_gate": lambda self, i: gate})())
        res = TestClient(app).post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": quantity})
        return res, added
    return call


def test_tc2_14_cart_add_counts_every_row(add_to_cart):
    res, added = add_to_cart(quantity=2, stock=3)          # 2 in the cart + 2 > 3
    assert res.status_code == 409 and added == []
    assert res.json()["detail"] == {"code": "portions_left", "message": "Only 3 portion(s) left: Adobo", "name": "Adobo", "remaining": 3}
    res, added = add_to_cart(quantity=1, stock=3)
    assert res.status_code == 200 and added == [1]


def test_tc2_15_cart_add_preorder_checked_too(add_to_cart):
    res, added = add_to_cart(quantity=1, stock=1, in_cart=0, preorder_day=2)
    assert res.status_code == 200 and added == [1]
    res, _ = add_to_cart(quantity=1, stock=1, in_cart=1, preorder_day=2)
    assert res.status_code == 409


@pytest.mark.parametrize("stock, min_quantity", [(0, 1), (2, 3)])
def test_tc2_41_sold_out_refused_like_off_sale(add_to_cart, stock, min_quantity):
    res, added = add_to_cart(quantity=1, stock=stock, in_cart=0, min_quantity=min_quantity)
    assert res.status_code == 400 and res.json()["detail"] == "This dish is sold out" and added == []


def test_cart_add_no_limit(add_to_cart):
    res, added = add_to_cart(quantity=9, stock=None)
    assert res.status_code == 200 and added == [9]


# ─── POST /payments/vnpay/create (QĐ2-8 c) ────────────────────────────────────
def _items(stock, quantities=(2,)):
    return [{"food_item_id": "food-1", "quantity": q, "name_snapshot": "Adobo", "food_items": {"stock": stock}} for q in quantities]


@pytest.mark.parametrize("calls", [1, 20])
def test_tc2_18_tc2_45_no_link_when_short(env, pay_client, calls):
    env.orders = FakeOrders(order_items=_items(stock=3, quantities=(2, 2)))
    for _ in range(calls):
        res = pay_client.post(f"/payments/vnpay/create/{OID}")
        assert res.status_code == 409
        assert res.json()["detail"] == {"code": "stock_short", "message": "Adobo just sold out", "name": "Adobo"}
    assert env.orders.links == [] and env.calls == []          # no link, VNPay not asked
    assert env.orders.order["status"] == "pending"             # the order stays, it holds no stock


def test_tc2_19_enough_stock_makes_the_link(env, pay_client):
    env.orders = FakeOrders(order_items=_items(stock=5), payments=[{"transaction_ref": env.txn, "status": "failed"}])
    res = pay_client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 200 and res.json()["payment_url"] and len(env.orders.links) == 1


# ─── Seller PATCH (QĐ2-11, BM12) ──────────────────────────────────────────────
@pytest.mark.parametrize("body, status, want", [
    ({"stock": 5}, 200, {"stock": 5, "stock_alert_at": None}),        # P1: a new count clears the last push time
    ({"stock": None}, 200, {"stock": None, "stock_alert_at": None}),  # TC2-31: null clears the limit
    ({"price": 60000}, 200, {"price": 60000, "price_text": "60.000 ₫"}),   # TC2-31: left out, the stock is untouched
    ({"stock": 0}, 200, {"stock": 0, "stock_alert_at": None}),
    ({"stock": -1}, 422, None),
    ({"stock": 100001}, 422, None),
    ({"stock": 1.5}, 422, None),
    ({"stock": "a"}, 422, None),
    ({"name": "Adobo", "daily_portions": 3}, 200, {"name": "Adobo"}),   # an old app's field: ignored
])
def test_tc2_22_patch_stock(monkeypatch, body, status, want):
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")
    sent = []

    def update(self, item_id, seller_id, fields):
        sent.append(fields)
        return {"id": item_id, "stock": fields.get("stock", 6), "min_quantity": 1} if item_id == "food-1" else None
    monkeypatch.setattr("apis.sellers.DAOFoodItems", lambda: type("F", (), {"update": update})())
    res = TestClient(app).patch("/sellers/me/menu/items/food-1", json=body)
    assert res.status_code == status
    assert sent == ([want] if want else [])
    if status == 200:
        assert "sold_out" in res.json()["item"]
    if body == {"stock": 5}:   # another store's dish: the DAO's seller filter finds nothing
        assert TestClient(app).patch("/sellers/me/menu/items/food-2", json=body).status_code == 404


def test_create_ignores_daily_portions(monkeypatch):
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")
    sent = []
    monkeypatch.setattr("apis.sellers.DAOFoodItems", lambda: type("F", (), {
        "create": lambda self, seller_id, fields: sent.append(fields) or {"id": "food-1", **fields}})())
    res = TestClient(app).post("/sellers/me/menu/items", json={"name": "Adobo", "price": 50000, "stock": 4, "daily_portions": 9})
    assert res.status_code == 200 and sent[0]["stock"] == 4 and "daily_portions" not in sent[0]


# ─── Reads: sold_out from the row, no RPC (TC2-23, TC2-42) ────────────────────
class _NoRpc:
    """A Supabase client whose table reads answer `rows` and whose rpc() fails the test."""

    def __init__(self, rows):
        self.rows = rows

    def rpc(self, *a, **k):
        raise AssertionError("no RPC on a menu read")

    def table(self, name):
        rows = self.rows

        class Q:
            def __getattr__(self, attr):
                return lambda *a, **k: self

            def execute(self):
                return _Result(rows)
        return Q()


def _dao(rows):
    dao = DAOFoodItems.__new__(DAOFoodItems)
    dao._table_name, dao._supabase_client = "food_items", _NoRpc(rows)
    return dao


def test_tc2_23_menu_read(monkeypatch):
    menu = [{"id": "c", "food_items": [{"id": "a", "stock": 0, "min_quantity": 1}, {"id": "b", "stock": None, "min_quantity": 2}]}]
    out = _dao(menu).read_menu_by_seller_id("seller-1")
    assert [(f["sold_out"], f["stock"]) for f in out[0]["food_items"]] == [(True, 0), (False, None)]
    assert not any("remaining_today" in f for f in out[0]["food_items"])
    assert _dao([{"id": "c", "food_items": []}]).read_menu_by_seller_id("seller-1") == [{"id": "c", "food_items": []}]


def test_tc2_42_featured_dishes(monkeypatch):
    rows = [{"id": "1", "stock": 0, "min_quantity": 1}, {"id": "2", "stock": 2, "min_quantity": 3}, {"id": "3", "stock": 5, "min_quantity": 1}]
    assert [d["sold_out"] for d in _dao(rows).read_featured_dishes()] == [True, True, False]


def test_tc2_23_cart_read(monkeypatch):
    cart_row = _cart([3], stock=2)
    monkeypatch.setattr(cart, "DAOCartItems", lambda: type("D", (), {"read_cart_items_by_user_id": lambda self, user_id: cart_row})())
    food = cart.get_current_cart({"id": "u1"})["cart"]["cart_items"][0]["food_items"]
    assert (food["stock"], food["min_quantity"], food["sold_out"]) == (2, 1, False) and "remaining_today" not in food


def test_add_sold_out_skips_a_deleted_dish():
    assert add_sold_out([None, {"stock": 0}]) == [None, {"stock": 0, "sold_out": True}]
