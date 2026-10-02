"""Money-path checks for price variants. No DB, no network.

Run from backend/src:  python -m pytest tests/test_pricing.py   (or: python tests/test_pricing.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# core.auth refuses to import without this; the value is never fetched here.
os.environ.setdefault("SUPABASE_JWKS_URL", "https://test.invalid/jwks")

from fastapi import HTTPException

import apis.cart as cart
from apis.orders import unavailable_names
from utils.pricing import cart_item_unit_price


def test_unit_price_prefers_variant():
    dish = {"price": 50000}
    assert cart_item_unit_price({"food_items": dish, "food_item_variants": None}) == 50000
    assert cart_item_unit_price({"food_items": dish, "food_item_variants": {"price": 80000}}) == 80000
    assert cart_item_unit_price({"food_items": dish}) == 50000


def test_subtotal_matches_sum_of_snapshots():
    items = [
        {"quantity": 2, "food_items": {"price": 50000}, "food_item_variants": {"price": 80000}},
        {"quantity": 1, "food_items": {"price": 25000}, "food_item_variants": None},
    ]
    subtotal = sum(cart_item_unit_price(i) * i["quantity"] for i in items)
    assert subtotal == 185000


def _guard(variants, variant_id):
    class FakeDAO:
        def read_by_food_item_id(self, _):
            return variants
    real, cart.DAOFoodItemVariants = cart.DAOFoodItemVariants, FakeDAO
    try:
        cart._validate_variant("dish", variant_id)
        return None
    except HTTPException as e:
        return e.detail
    finally:
        cart.DAOFoodItemVariants = real


def test_variant_guard():
    levels = [{"id": "S", "is_available": True}, {"id": "XL", "is_available": False}]
    assert _guard([], None) is None                                    # no levels, none sent
    assert _guard([], "S") == "This dish has no price options"
    assert _guard(levels, "S") is None
    assert _guard(levels, None) == "Please choose a price option"      # the hole this guard exists for
    assert _guard(levels, "other") == "Invalid price option for this dish"
    assert _guard(levels, "XL") == "This price option is sold out"


def test_unavailable_names():
    ok = {"food_items": {"name": "Chè", "is_available": True}, "food_item_variants": None}
    dish_off = {"food_items": {"name": "Bún", "is_available": False}, "food_item_variants": None}
    level_off = {"food_items": {"name": "Bún", "is_available": True},
                 "food_item_variants": {"name": "L", "is_available": False}}
    assert unavailable_names([ok]) == []
    assert unavailable_names([dish_off]) == ["Bún"]
    assert unavailable_names([level_off]) == ["Bún (L)"]
    assert unavailable_names([ok, dish_off, level_off]) == ["Bún", "Bún (L)"]


if __name__ == "__main__":
    test_unit_price_prefers_variant()
    test_subtotal_matches_sum_of_snapshots()
    test_variant_guard()
    test_unavailable_names()
    print("ok")
