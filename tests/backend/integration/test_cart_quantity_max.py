"""TC-1 (docs/dev/20261102-security-fixes S1): one dish is capped at cart_max_quantity_per_item at cart add,
cart update and order create; over it -> 400 quantity_max and nothing is written. Since option groups the cap is
the dish over all its cart rows (seller-menu đợt 3 QĐ3-4b); at /cart/add the database checks it (add_cart_item)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import cart, orders
from core.auth import verify_token
from dao.dao_cart_items import CartLimit

MAX = 50


LINE = "00000000-0000-4000-8000-000000000001"


class _Settings:
    def get_positive_int(self, key, default):
        return MAX if key == "cart_max_quantity_per_item" else default


class _FakeCarts:
    def read_cart_by_user_id_seller_id(self, user_id):
        return {"id": "cart-1", "seller_id": "seller-1"}


class _FakeCartItems:
    refuse = None
    writes = []
    cart_rows = []
    lines = []

    def add_item(self, cart_id, food_item_id, variant_id, option_ids, quantity, max_quantity, max_lines):
        if _FakeCartItems.refuse:
            raise CartLimit(_FakeCartItems.refuse)
        _FakeCartItems.writes.append((quantity, max_quantity, max_lines))

    def read_lines(self, cart_id):
        return _FakeCartItems.lines

    def update_quantity(self, cart_id, item_id, quantity):
        _FakeCartItems.writes.append(quantity)
        return [{"id": item_id}]

    def read_cart_items_by_user_id(self, user_id):
        return {"id": "cart-1", "seller_id": "seller-1", "cart_items": _FakeCartItems.cart_rows}


class _FakeOrders:
    created = []

    def read_orders_by_user_id(self, user_id):
        return []

    def create_order(self, **kw):
        _FakeOrders.created.append(kw)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    monkeypatch.setattr("apis.orders.DAOAdminConfig", _Settings)
    monkeypatch.setattr("apis.cart._validate_variant", lambda *a: None)
    gate = {"seller_id": "seller-1", "is_available": True, "preorder_day": 1,
            "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70, "is_open": True}}
    monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("D", (), {"read_order_gate": lambda self, i: gate})())
    monkeypatch.setattr("apis.cart.DAOCarts", _FakeCarts)
    monkeypatch.setattr("apis.cart.DAOCartItems", _FakeCartItems)
    monkeypatch.setattr("apis.orders.DAOCartItems", _FakeCartItems)
    monkeypatch.setattr("apis.orders.DAOOrders", _FakeOrders)
    _FakeCartItems.refuse, _FakeCartItems.writes, _FakeOrders.created = None, [], []
    _FakeCartItems.lines = [{"id": LINE, "food_item_id": "food-1", "variant_id": None, "option_ids": [], "quantity": 1}]
    return TestClient(app)


def _add(client, quantity):
    return client.post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": quantity})


def _is_quantity_max(res):
    return res.status_code == 400 and res.json()["detail"] == {
        "code": "quantity_max", "message": f"At most {MAX} of each dish", "max": MAX}


def test_add_at_max_is_taken(client):
    assert _add(client, MAX).status_code == 200
    assert _FakeCartItems.writes == [(MAX, MAX, 20)]   # the caps the database checks the dish total and rows against


def test_add_over_max_is_refused(client):
    assert _is_quantity_max(_add(client, 1_000_000))
    assert _FakeCartItems.writes == []


def test_add_counts_what_is_already_in_the_cart(client):
    _FakeCartItems.refuse = "quantity_max"   # add_cart_item: the dish's rows + this add pass the cap
    assert _is_quantity_max(_add(client, 2))
    assert _FakeCartItems.writes == []


def test_add_over_the_rows_cap_is_refused(client):   # TC3-64
    _FakeCartItems.refuse = "cart_max_lines"
    res = _add(client, 1)
    assert res.status_code == 400 and res.json()["detail"] == {
        "code": "cart_max_lines", "message": "At most 20 different dishes in one cart", "max": 20}


@pytest.mark.parametrize("quantity", [0, -5, None])
def test_add_needs_a_positive_quantity(client, quantity):
    assert _add(client, quantity).status_code == 422
    assert _FakeCartItems.writes == []


def test_update_over_max_is_refused(client):
    res = client.patch("/cart/update", json={"id": LINE, "quantity": MAX + 1})
    assert _is_quantity_max(res)
    assert _FakeCartItems.writes == []


def test_update_counts_the_dish_other_rows(client):   # TC3-61: rows 30 + 10, the 10 -> 25 is 55
    other = "00000000-0000-4000-8000-000000000002"
    _FakeCartItems.lines = [{"id": LINE, "food_item_id": "food-1", "variant_id": None, "option_ids": ["a"], "quantity": 30},
                            {"id": other, "food_item_id": "food-1", "variant_id": None, "option_ids": [], "quantity": 10}]
    assert _is_quantity_max(client.patch("/cart/update", json={"id": other, "quantity": 25}))
    assert client.patch("/cart/update", json={"id": LINE, "quantity": 20}).status_code == 200
    assert _FakeCartItems.writes == [20]


def test_order_from_an_old_oversized_cart_is_refused(client):
    _FakeCartItems.cart_rows = [
        {"quantity": 2, "food_items": {"id": "food-1", "name": "Adobo"}},
        {"quantity": 1_000_000, "food_items": {"id": "food-2", "name": "Lechon"}},
    ]
    assert _is_quantity_max(client.post("/orders", json={"delivery_method": "pickup"}))
    assert _FakeOrders.created == []
