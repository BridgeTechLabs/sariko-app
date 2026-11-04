"""TC-6 fixes-1021 (T13): GET /cart carries is_available for each dish and price level,
so the cart page can mark what the seller switched off after it went into the cart.
No DB, no network.

Run from tests/backend:  pytest unit/test_cart_availability.py
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import apis.cart as cart_api
import apis.orders as orders
from core.auth import verify_token
from dao.dao_cart_items import DAOCartItems

ROWS = {
    "id": "c1", "seller_id": "s1",
    "cart_items": [
        {"quantity": 1, "variant_id": None,
         "food_items": {"id": "f1", "name": "Adobo", "is_available": False}, "food_item_variants": None},
        {"quantity": 2, "variant_id": "v1",
         "food_items": {"id": "f2", "name": "Sinigang", "is_available": True},
         "food_item_variants": {"id": "v1", "name": "Large", "is_available": False}},
    ],
}


class FakeQuery:
    def __init__(self):
        self.select_arg = None

    def select(self, arg):
        self.select_arg = arg
        return self

    def eq(self, *_): return self
    def limit(self, *_): return self
    def execute(self):
        return type("R", (), {"data": [ROWS]})()


def test_dao_selects_is_available_on_dish_and_level(monkeypatch):
    query = FakeQuery()
    dao = DAOCartItems.__new__(DAOCartItems)
    dao._supabase_client = type("C", (), {"table": lambda self, name: query})()
    assert dao.read_cart_items_by_user_id("u") == ROWS
    food, level = query.select_arg.split("food_items(")[1].split("food_item_variants(")
    assert "is_available" in food and "is_available" in level


def test_get_cart_returns_flags(monkeypatch):
    monkeypatch.setattr(cart_api.DAOCartItems, "read_cart_items_by_user_id", lambda self, user_id: ROWS)
    app = FastAPI()
    app.include_router(cart_api.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "u"}
    items = TestClient(app).get("/cart").json()["cart"]["cart_items"]
    assert items[0]["food_items"]["is_available"] is False
    assert items[1]["food_item_variants"]["is_available"] is False


def test_unavailable_names_same_wording_as_cart_page():
    assert orders.unavailable_names(ROWS["cart_items"]) == ["Adobo", "Sinigang (Large)"]
