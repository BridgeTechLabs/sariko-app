"""A duplicate dish name (DB unique_violation) must surface as FoodItemNameTaken,
which the API turns into a 409. No DB, no network.

Run from backend/src:  python -m pytest tests/test_food_item_name_taken.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from postgrest.exceptions import APIError

from dao.dao_food_items import DAOFoodItems, FoodItemNameTaken


class _Query:
    """Stands in for the postgrest builder: every chained call returns itself, execute() raises."""

    def __init__(self, code):
        self._code = code

    def __getattr__(self, _name):
        return lambda *a, **kw: self

    def execute(self):
        raise APIError({"code": self._code, "message": "boom"})


def _dao(code):
    dao = DAOFoodItems.__new__(DAOFoodItems)  # skip __init__: no Supabase client
    dao._table_name = "food_items"
    dao._supabase_client = _Query(code)
    return dao


def test_duplicate_name_on_create_and_update():
    with pytest.raises(FoodItemNameTaken):
        _dao("23505").create("seller", {"name": "Leche flan"})
    with pytest.raises(FoodItemNameTaken):
        _dao("23505").update("item", "seller", {"name": "Leche flan"})


def test_other_db_errors_pass_through():
    with pytest.raises(APIError):
        _dao("23503").create("seller", {"name": "Leche flan"})
