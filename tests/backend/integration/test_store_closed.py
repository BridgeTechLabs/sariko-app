"""A closed store blocks same-day dishes but still takes pre-orders (cart add + order create)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import cart
from apis.orders import same_day_names
from core.auth import verify_token


class _FakeCarts:
    def read_cart_by_user_id_seller_id(self, user_id):
        return {"id": "cart-1", "seller_id": "seller-1"}


class _FakeCartItems:
    added = []

    def add_item(self, cart_id, food_item_id, *rest):
        _FakeCartItems.added.append(food_item_id)


@pytest.fixture
def add_to_cart(monkeypatch):
    """POST /cart/add with the dish's gate row faked; returns (response, added food ids)."""
    app = FastAPI()
    app.include_router(cart.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    client = TestClient(app)
    monkeypatch.setattr("apis.cart._validate_variant", lambda *a: None)
    monkeypatch.setattr("apis.cart.DAOCarts", _FakeCarts)
    monkeypatch.setattr("apis.cart.DAOCartItems", _FakeCartItems)
    monkeypatch.setattr("apis.orders.DAOAdminConfig", lambda: type("S", (), {"get_positive_int": lambda self, k, d: d})())

    def call(preorder_day, is_open, weekly_hours=None, is_available=True):
        _FakeCartItems.added = []
        gate = {"seller_id": "seller-1", "is_available": is_available, "preorder_day": preorder_day,
                "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70,
                                    "is_open": is_open, "weekly_hours": weekly_hours}}
        monkeypatch.setattr("apis.cart.DAOFoodItems", lambda: type("D", (), {"read_order_gate": lambda self, i: gate})())
        res = client.post("/cart/add", json={"seller_id": "seller-1", "food_item_id": "food-1", "quantity": 1})
        return res, _FakeCartItems.added
    return call


def test_closed_store_blocks_same_day_dish(add_to_cart):
    res, added = add_to_cart(preorder_day=0, is_open=False)
    assert res.status_code == 400
    assert "closed" in res.json()["detail"]
    assert added == []


def test_closed_store_still_takes_preorders(add_to_cart):
    res, added = add_to_cart(preorder_day=2, is_open=False)
    assert res.status_code == 200
    assert added == ["food-1"]


def test_open_store_takes_same_day(add_to_cart):
    res, added = add_to_cart(preorder_day=0, is_open=True)
    assert res.status_code == 200
    assert added == ["food-1"]


def test_order_create_flags_only_same_day_items():
    items = [
        {"food_items": {"name": "Adobo", "preorder_day": 0}},
        {"food_items": {"name": "Lechon", "preorder_day": 3}},
        {"food_items": {"name": "Pancit", "preorder_day": None}},
    ]
    assert same_day_names(items) == ["Adobo", "Pancit"]


def _week_with_today(today_hours):
    """Every day open all day (open = close) except today; yesterday too, so nothing runs past midnight."""
    from datetime import datetime, timedelta
    from core.store_hours import VN_TZ
    today = datetime.now(VN_TZ)
    week = {str(d): {"open": "00:00", "close": "00:00"} for d in range(1, 8)}
    week[str((today - timedelta(days=1)).isoweekday())] = None
    week[str(today.isoweekday())] = today_hours
    return week


def test_switch_on_but_outside_hours_blocks_same_day(add_to_cart):
    # Today's slot = 1 minute starting 5 min from now, so "now" is outside it
    from datetime import datetime, timedelta
    from core.store_hours import VN_TZ
    now = datetime.now(VN_TZ)
    if now.strftime("%H:%M") >= "23:50":
        pytest.skip("the slot would cross midnight")
    slot = {"open": (now + timedelta(minutes=5)).strftime("%H:%M"), "close": (now + timedelta(minutes=6)).strftime("%H:%M")}
    res, added = add_to_cart(preorder_day=0, is_open=True, weekly_hours=_week_with_today(slot))
    assert res.status_code == 400
    assert added == []


def test_day_off_blocks_same_day_but_takes_preorders(add_to_cart):
    week = _week_with_today(None)
    res, added = add_to_cart(preorder_day=0, is_open=True, weekly_hours=week)
    assert res.status_code == 400 and added == []
    res, added = add_to_cart(preorder_day=2, is_open=True, weekly_hours=week)
    assert res.status_code == 200 and added == ["food-1"]


def test_sold_out_dish_blocked_even_when_open(add_to_cart):
    res, added = add_to_cart(preorder_day=0, is_open=True, is_available=False)
    assert res.status_code == 400
    assert "sold out" in res.json()["detail"]
    assert added == []
