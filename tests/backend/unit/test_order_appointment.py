"""T127: POST /orders refuses a cart with a pre-order dish (preorder_day > 0) without a delivery appointment
at least that many days ahead, the cart page's rule. Fakes from test_order_delivery_fee (no DB, no network)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import apis.orders as orders
from schemas import Schema
from test_order_delivery_fee import created, fakes  # noqa: F401  (autouse fixture: fake DAOs)

NOW = datetime.now(timezone.utc)


def cart(*preorder_days):
    return {"id": "cart", "seller_id": "seller", "cart_items": [
        {"quantity": 1, "food_items": {"name": f"Dish {d}", "price": 50000, "is_available": True, "preorder_day": d},
         "food_item_variants": None} for d in preorder_days]}


def place(monkeypatch, items, appointment):
    monkeypatch.setattr(orders, "DAOCartItems", lambda: type("C", (), {"read_cart_items_by_user_id": lambda self, user_id: items})())
    req = Schema.RequestCreateOrder(delivery_method="pickup", delivery_appointment=appointment)
    return orders.create_order(req, user={"id": "buyer"})


def refused(monkeypatch, items, appointment):
    with pytest.raises(HTTPException) as e:
        place(monkeypatch, items, appointment)
    assert e.value.status_code == 400 and created == []
    return e.value.detail


def test_preorder_without_appointment_is_400(monkeypatch):
    assert refused(monkeypatch, cart(0, 2), None) == {
        "code": "appointment_required", "message": "Choose a delivery date and time for pre-order dishes", "days": 2}


def test_appointment_too_early_uses_the_largest_preorder_day(monkeypatch):
    detail = refused(monkeypatch, cart(1, 3), NOW + timedelta(days=2))
    assert (detail["code"], detail["days"]) == ("appointment_too_early", 3)


def test_appointment_in_the_past_is_400(monkeypatch):
    assert refused(monkeypatch, cart(1), NOW - timedelta(hours=1))["code"] == "appointment_past"


def test_appointment_far_enough_creates_the_order(monkeypatch):
    assert place(monkeypatch, cart(0, 2), NOW + timedelta(days=2, hours=1))["success"]
    assert created[-1]["delivery_appointment"] == NOW + timedelta(days=2, hours=1)


def test_cart_page_minimum_a_few_minutes_old_still_passes(monkeypatch):
    # the page computed now + 1 day when it opened; the order arrives 10 minutes later
    assert place(monkeypatch, cart(1), NOW + timedelta(days=1) - timedelta(minutes=10))["success"]


def test_same_day_only_needs_no_appointment(monkeypatch):
    assert place(monkeypatch, cart(0, None), None)["success"]


def test_naive_time_is_vietnam_time(monkeypatch):
    local = (NOW + timedelta(days=2)).astimezone(timezone(timedelta(hours=7))).replace(tzinfo=None)
    assert place(monkeypatch, cart(1), local)["success"]
    assert created[-1]["delivery_appointment"].utcoffset() == timedelta(hours=7)
