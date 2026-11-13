"""T210 (seller-menu đợt 4A C1, QĐ4-10, TC4-33): POST /cart/add when the cart is deleted between reading it and adding
to it (the same buyer clears it, or places the order, in another tab): the add goes to the buyer's cart read / made again,
once. Seen on DEV 13/11: a DELETE /cart/clear in the same second as a /cart/add -> cart_items_cart_id_fkey (23503) -> 500."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from apis import cart
from core.auth import verify_token
from dao.dao_cart_items import CartGone, DAOCartItems

GATE = {"seller_id": "seller-1", "name": "Adobo", "is_available": True, "preorder_day": 0, "stock": None, "min_quantity": 1,
        "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70, "is_open": True}}


@pytest.fixture
def add(monkeypatch):
    """carts = what read_cart_by_user_id_seller_id answers, one per call; fails = how many adds hit a deleted cart."""
    app = FastAPI()
    app.include_router(cart.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    monkeypatch.setattr("apis.cart._validate_variant", lambda *a: None)
    monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("G", (), {"read_order_gate": lambda self, i: GATE})())
    monkeypatch.setattr("apis.orders.DAOAdminConfig", lambda: type("C", (), {"get_positive_int": lambda self, k, d: d})())

    def call(carts, fails):
        state = {"reads": list(carts), "made": [], "adds": []}
        monkeypatch.setattr("apis.cart.DAOCarts", lambda: type("Ca", (), {
            "read_cart_by_user_id_seller_id": lambda self, user_id: state["reads"].pop(0),
            "create_cart": lambda self, user_id, seller_id: state["made"].append(seller_id) or {"id": f"new-{len(state['made'])}"},
        })())

        def add_item(self, cart_id, *a):
            state["adds"].append(cart_id)
            if len(state["adds"]) <= fails:
                raise CartGone()
        monkeypatch.setattr("apis.cart.DAOCartItems", lambda: type("CI", (), {"add_item": add_item})())
        res = TestClient(app).post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": 1})
        return res, state
    return call


def test_tc4_33_deleted_cart_add_goes_to_a_new_cart_once(add):
    res, state = add(carts=[{"id": "old", "seller_id": "seller-1"}, None], fails=1)
    assert res.status_code == 200
    assert state["adds"] == ["old", "new-1"] and state["made"] == ["seller-1"]   # 2 adds, the second into the new cart


def test_the_store_rule_holds_on_the_second_try(add):
    # the other tab cleared the cart and filled it with another store's dish: the usual "switch store" answer
    other = {"id": "other", "seller_id": "seller-2", "seller_profiles": {"store_name": "Bếp B"}}
    res, state = add(carts=[{"id": "old", "seller_id": "seller-1"}, other], fails=1)
    assert res.status_code == 400 and res.json()["detail"]["message"] == "Cart contains items from another seller"
    assert state["adds"] == ["old"]


def test_a_second_failure_is_an_error_as_before(add):
    with pytest.raises(CartGone):
        add(carts=[{"id": "old", "seller_id": "seller-1"}, {"id": "gone-too", "seller_id": "seller-1"}], fails=2)


def test_dao_maps_the_foreign_key_error():
    dao = DAOCartItems.__new__(DAOCartItems)

    class Rpc:
        def execute(self):
            raise APIError({"message": 'insert or update on table "cart_items" violates foreign key constraint '
                                       '"cart_items_cart_id_fkey"', "code": "23503", "hint": None, "details": None})
    dao._supabase_client = type("C", (), {"rpc": lambda self, name, params: Rpc()})()
    with pytest.raises(CartGone):
        dao.add_item("old", "food-1", None, [], 1, 50, 20)
