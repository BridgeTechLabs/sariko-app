"""TC-1 (docs/dev/20261102-security-fixes S1): one cart row is capped at cart_max_quantity_per_item at cart add,
cart update and order create; over it -> 400 quantity_max and nothing is written."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import cart, orders
from core.auth import verify_token

MAX = 50


class _Settings:
    def get_positive_int(self, key, default):
        assert key == "cart_max_quantity_per_item"
        return MAX


class _FakeCarts:
    def read_cart_by_user_id_seller_id(self, user_id):
        return {"id": "cart-1", "seller_id": "seller-1"}


class _FakeCartItems:
    existing = None
    writes = []
    cart_rows = []

    def find_item(self, **kw):
        return _FakeCartItems.existing

    def update_food_item_by_cart_id(self, **kw):
        _FakeCartItems.writes.append(kw["quantity"])

    def update_quantity(self, **kw):
        _FakeCartItems.writes.append(kw["quantity"])

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
    monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("D", (), {"read_order_gate": lambda self, i: None})())
    monkeypatch.setattr("apis.cart.DAOCarts", _FakeCarts)
    monkeypatch.setattr("apis.cart.DAOCartItems", _FakeCartItems)
    monkeypatch.setattr("apis.orders.DAOCartItems", _FakeCartItems)
    monkeypatch.setattr("apis.orders.DAOOrders", _FakeOrders)
    _FakeCartItems.existing, _FakeCartItems.writes, _FakeOrders.created = None, [], []
    return TestClient(app)


def _add(client, quantity):
    return client.post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": quantity})


def _is_quantity_max(res):
    return res.status_code == 400 and res.json()["detail"] == {
        "code": "quantity_max", "message": f"At most {MAX} of each dish", "max": MAX}


def test_add_at_max_is_taken(client):
    assert _add(client, MAX).status_code == 200
    assert _FakeCartItems.writes == [MAX]


def test_add_over_max_is_refused(client):
    assert _is_quantity_max(_add(client, 1_000_000))
    assert _FakeCartItems.writes == []


def test_add_counts_what_is_already_in_the_cart(client):
    _FakeCartItems.existing = {"quantity": MAX - 1}
    assert _is_quantity_max(_add(client, 2))
    assert _FakeCartItems.writes == []


@pytest.mark.parametrize("quantity", [0, -5, None])
def test_add_needs_a_positive_quantity(client, quantity):
    assert _add(client, quantity).status_code == 422
    assert _FakeCartItems.writes == []


def test_update_over_max_is_refused(client):
    res = client.patch("/cart/update", json={"food_item_id": "food-1", "quantity": MAX + 1})
    assert _is_quantity_max(res)
    assert _FakeCartItems.writes == []


def test_order_from_an_old_oversized_cart_is_refused(client):
    _FakeCartItems.cart_rows = [
        {"quantity": 2, "food_items": {"id": "food-1", "name": "Adobo"}},
        {"quantity": 1_000_000, "food_items": {"id": "food-2", "name": "Lechon"}},
    ]
    assert _is_quantity_max(client.post("/orders", json={"delivery_method": "pickup"}))
    assert _FakeOrders.created == []
