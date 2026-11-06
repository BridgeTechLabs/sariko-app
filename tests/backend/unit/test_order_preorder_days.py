"""20261106-order-scheduled: buyer order reads carry preorder_days = the largest live preorder_day
of the order's dishes (the buyer UI shows "Scheduled" until the cooking day)."""
import copy

import pytest

from dao.dao_orders import DAOOrders


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    def execute(self):
        return self


def fake_dao(data):
    dao = DAOOrders.__new__(DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, t: FakeQuery(copy.deepcopy(data))})()
    return dao


def items(*days):
    return [{"food_items": None if d == "deleted" else {"preorder_day": d}} for d in days]


@pytest.mark.parametrize("days, expected", [
    ((2, 0), 2),               # TC-1: pre-order + same-day dish
    ((0, None), 0),            # TC-2: same-day only (0 / null)
    (("deleted", 0), 0),       # TC-2: deleted dish doesn't count, no error
    (("deleted", 3), 3),
    ((), 0),
])
def test_preorder_days(days, expected):
    order = {"id": "o1", "order_items": items(*days)}
    assert fake_dao(order).read_order_by_id("o1", "u1")["preorder_days"] == expected
    assert [o["preorder_days"] for o in fake_dao([order, {"id": "o2", "order_items": []}]).read_orders_by_user_id("u1")] == [expected, 0]


def test_not_found():
    assert fake_dao(None).read_order_by_id("o1", "u1") is None
    assert fake_dao([]).read_orders_by_user_id("u1") == []
