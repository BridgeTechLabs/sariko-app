"""T134 daily portions (docs/dev/daily-portions): the paid path takes the portions and cancels + refunds an order
whose last portion went while the buyer paid (TC-8), the early 409 at cart add / order create (TC-9), the seller
PATCH and remaining_today. The SQL itself (reserve / trigger, TC-1..7) is checked on DEV."""
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import apis.orders as orders
from apis import cart, sellers
from core.auth import verify_token
from core.store_hours import VN_TZ
from dao.dao_food_items import DAOFoodItems
from dao.dao_orders import DAOOrders
from dao.dao_refunds import DAORefunds
from schemas import Schema
from test_order_delivery_fee import created, fakes  # noqa: F401  (autouse fixture: fake DAOs for POST /orders)

ORDER_ID = "abc12345-678a-4bcd-9012-345678901234"


def make_ipn_params(secret, order_id, amount_vnd):
    """A signed paid IPN (same signing as integration/test_payments_ipn.py)."""
    from apis.payments import _hmac_sha512
    params = {"vnp_Amount": str(amount_vnd * 100), "vnp_PayDate": "20260430120500", "vnp_ResponseCode": "00",
              "vnp_TmnCode": "TEST_TMN", "vnp_TransactionNo": "14567890", "vnp_TransactionStatus": "00",
              "vnp_TxnRef": f"{order_id.replace('-', '')}_20260430120000"}
    data = "&".join(f"{urllib.parse.quote_plus(k, safe='')}={urllib.parse.quote_plus(v, safe='')}" for k, v in sorted(params.items()))
    return params | {"vnp_SecureHash": _hmac_sha512(secret, data)}


# ─── TC-8: IPN paid, reserve false ────────────────────────────────────────────
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
    def __init__(self, reserve):
        self.reserve, self.calls = reserve, []
        self.order = {"id": ORDER_ID, "user_id": "buyer", "seller_user_id": "seller", "status": "pending",
                      "payment_status": "pending", "total_amount": "100000", "transaction_ref": None,
                      "ipn_data": None, "payment_create_date": "20260430120000"}

    def rpc(self, name, params):
        self.calls.append(("rpc", name))
        if name == "reserve_order_portions":
            return _Result(self.reserve)
        if name == "update_order_payment_status":
            self.order.update(payment_status=params["p_status"], transaction_ref=params["p_transaction_ref"])
        return _Result(None)

    def table(self, name):
        return _Query(self)


@pytest.fixture
def ipn(fastapi_client, vnp_secret, monkeypatch):
    """A paid IPN through apply_vnpay_result and the real DAOOrders on a fake client."""
    def call(reserve):
        client = _Client(reserve)
        dao = DAOOrders.__new__(DAOOrders)
        dao._table_name, dao._supabase_client = "orders", client
        monkeypatch.setattr(dao, "_invalidate_cache_for_order", lambda order_id: None, raising=False)
        monkeypatch.setattr("dao.dao_orders._invalidate_seller_orders", lambda seller_id: None)
        monkeypatch.setattr("apis.payments.DAOOrders", lambda: dao)
        monkeypatch.setattr("apis.payments.DAOPayments", lambda: type("P", (), {"create_payment": lambda self, **kw: None})())
        pushes, refunds = [], []
        monkeypatch.setattr("dao.dao_orders.push_service.notify_new_order", lambda order: pushes.append("new_order"))
        monkeypatch.setattr("dao.dao_orders.push_service.notify_order_status", lambda order: pushes.append(order["status"]))
        monkeypatch.setattr(DAORefunds, "__init__", lambda self: None)
        monkeypatch.setattr(DAORefunds, "create_refund", lambda self, **kw: refunds.append(kw))
        params = make_ipn_params(vnp_secret, ORDER_ID, 100000)
        res = fastapi_client.get("/payments/vnpay/ipn", params=params)
        return res.json(), client, pushes, refunds, params
    return call


def test_tc8_sold_out_while_paying(ipn):
    body, client, pushes, refunds, params = ipn(reserve=False)
    assert body["RspCode"] == "00"
    order = client.order
    assert (order["status"], order["cancellation_reason"], order["payment_status"]) == ("cancelled", "Sold out", "paid")
    [refund] = refunds
    assert (refund["order_id"], refund["amount"], refund["reason"]) == (ORDER_ID, Decimal("100000"), "sold_out")
    assert refund["original_txn_ref"] == params["vnp_TxnRef"]
    assert refund["ipn_data"]["vnp_TransactionNo"] == params["vnp_TransactionNo"]   # saved before the cancel
    assert pushes == ["cancelled"]                                                    # buyer told, no seller new-order push
    assert ("rpc", "compute_order_withholding") not in client.calls
    names = [c[1] for c in client.calls]
    assert names.index("reserve_order_portions") < names.index("update_order_payment_status")


def test_portions_taken_order_goes_to_seller(ipn):
    body, client, pushes, refunds, _ = ipn(reserve=True)
    assert body["RspCode"] == "00"
    assert (client.order["status"], client.order["payment_status"]) == ("pending", "paid")
    assert pushes == ["new_order"] and refunds == []
    assert ("rpc", "compute_order_withholding") in client.calls


# ─── TC-9: early 409 ──────────────────────────────────────────────────────────
def _portions_left(monkeypatch, module, left, asked):
    def read(self, ids, sale_date):
        asked.append((sorted(ids), sale_date))
        return left
    monkeypatch.setattr(module, "DAOFoodItems", lambda: type("F", (), {"read_portions_left": read})())


def _cart(qty_by_variant, preorder_day=0):
    return {"id": "cart", "seller_id": "seller", "cart_items": [
        {"quantity": q, "food_items": {"id": "food-1", "name": "Adobo", "price": 50000, "is_available": True,
                                       "preorder_day": preorder_day, "daily_portions": 5},
         "food_item_variants": None} for q in qty_by_variant]}


def test_tc9_create_order_sums_levels_of_a_dish(monkeypatch):
    asked = []
    _portions_left(monkeypatch, orders, {"food-1": 1}, asked)
    monkeypatch.setattr(orders, "DAOCartItems", lambda: type("C", (), {"read_cart_items_by_user_id": lambda self, user_id: _cart([1, 1])})())
    with pytest.raises(HTTPException) as e:
        orders.create_order(Schema.RequestCreateOrder(delivery_method="pickup"), user={"id": "buyer"})
    assert e.value.status_code == 409 and created == []
    assert e.value.detail == {"code": "portions_left", "message": "Only 1 portion(s) left: Adobo", "name": "Adobo", "remaining": 1}
    assert asked == [(["food-1"], datetime.now(VN_TZ).date())]


def test_tc7_preorder_checks_its_delivery_day(monkeypatch):
    asked = []
    _portions_left(monkeypatch, orders, {"food-1": 2}, asked)
    monkeypatch.setattr(orders, "DAOCartItems", lambda: type("C", (), {"read_cart_items_by_user_id": lambda self, user_id: _cart([2], 1)})())
    when = datetime.now(timezone.utc) + timedelta(days=2)
    res = orders.create_order(Schema.RequestCreateOrder(delivery_method="pickup", delivery_appointment=when), user={"id": "buyer"})
    assert res["success"] and len(created) == 1
    assert asked == [(["food-1"], when.astimezone(VN_TZ).date())]


@pytest.fixture
def add_to_cart(monkeypatch):
    app = FastAPI()
    app.include_router(cart.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    monkeypatch.setattr("apis.cart._validate_variant", lambda *a: None)
    added = []
    monkeypatch.setattr("apis.cart.DAOCarts", lambda: type("Ca", (), {
        "read_cart_by_user_id_seller_id": lambda self, user_id: {"id": "cart", "seller_id": "seller-1"}})())
    monkeypatch.setattr("apis.cart.DAOCartItems", lambda: type("CI", (), {
        "read_cart_items_by_user_id": lambda self, user_id: _cart([2]),
        "find_item": lambda self, **kw: None,
        "update_food_item_by_cart_id": lambda self, **kw: added.append(kw["quantity"])})())

    def call(quantity, left, preorder_day=0):
        gate = {"name": "Adobo", "is_available": True, "preorder_day": preorder_day, "daily_portions": 5,
                "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70, "is_open": True}}
        monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("G", (), {"read_order_gate": lambda self, i: gate})())
        asked = []
        _portions_left(monkeypatch, orders, {"food-1": left}, asked)
        res = TestClient(app).post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": quantity})
        return res, added, asked
    return call


def test_tc9_cart_add_counts_what_is_in_the_cart(add_to_cart):
    res, added, _ = add_to_cart(quantity=2, left=3)     # 2 in the cart + 2 > 3
    assert res.status_code == 409 and added == []
    assert res.json()["detail"]["remaining"] == 3
    res, added, _ = add_to_cart(quantity=1, left=3)
    assert res.status_code == 200 and added == [1]


def test_cart_add_preorder_not_checked(add_to_cart):
    res, added, asked = add_to_cart(quantity=9, left=0, preorder_day=1)
    assert res.status_code == 200 and asked == []


# ─── Q6: seller PATCH + remaining_today ───────────────────────────────────────
@pytest.mark.parametrize("body, want", [
    ({"daily_portions": 3}, {"daily_portions": 3}),
    ({"daily_portions": None}, {"daily_portions": None}),     # null clears the limit
    ({"name": "Adobo"}, {"name": "Adobo"}),                   # left out: unchanged
])
def test_patch_daily_portions(monkeypatch, body, want):
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-1")
    sent = []
    monkeypatch.setattr("apis.sellers.DAOFoodItems", lambda: type("F", (), {
        "update": lambda self, item_id, seller_id, fields: sent.append(fields) or {"id": item_id, **fields},
        "add_remaining_today": lambda self, items: items})())
    res = TestClient(app).patch("/sellers/me/menu/items/food-1", json=body)
    assert res.status_code == 200 and sent == [want]


def test_patch_rejects_zero():
    with pytest.raises(ValueError):
        Schema.RequestUpdateFoodItem(daily_portions=0)


def test_remaining_today(monkeypatch):
    asked = []

    def rpc(name, params):
        asked.append((name, params))
        return _Result([{"food_item_id": "a", "daily_portions": 5, "remaining": 2}])
    dao = DAOFoodItems.__new__(DAOFoodItems)
    dao._supabase_client = type("C", (), {"rpc": lambda self, n, p: rpc(n, p)})()
    items = [{"id": "a", "daily_portions": 5}, {"id": "b", "daily_portions": 4}, {"id": "c", "daily_portions": None}]
    dao.add_remaining_today(items)
    assert [i.get("remaining_today") for i in items] == [2, 4, None]
    assert asked == [("portions_left", {"p_food_item_ids": ["a", "b"], "p_sale_date": datetime.now(VN_TZ).date().isoformat()})]
    dao.add_remaining_today([{"id": "c"}])
    assert len(asked) == 1                                    # no limited dish: no DB call
