"""T178 (docs/dev/20261110-reason-texts): orders.cancellation_reason holds a CODE, translated for whoever reads it;
text a seller typed goes to cancellation_note (never shown to the buyer). No DB, no network."""
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

import apis.orders as orders
import apis.sellers as sellers
import dao.dao_orders as dao_orders
import dao.dao_refunds
import services.order_expiry as order_expiry
from schemas import Schema

SRC = Path(dao_orders.__file__).resolve().parent.parent
CODE = re.compile(r"^[a-z_]+$")


def test_a40a_system_cancels_write_codes():   # TC-A40a
    for value in (orders.SELLER_LATE_REASON, orders.DELIVERY_FAILED_REASON, orders.BUYER_CANCELLED_REASON,
                  order_expiry.TIMEOUT_REASON, dao_orders.SOLD_OUT_REASON, sellers.NO_DRIVER_REASON):
        assert CODE.match(value), value
    # no English sentence left as a cancellation_reason value in the backend
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r'_REASON\s*=\s*"[A-Z][a-z]+ ', text), path
        assert '"cancelled", "Driver booking failed"' not in text, path


class Orders:
    row, writes = None, []

    def read_order_by_id_for_seller(self, order_id, seller_id):
        return dict(Orders.row)

    def update_order_status(self, order_id, status, cancellation_reason=None, expected_status=None, cancellation_note=None):
        Orders.row = {**Orders.row, "status": status, "cancellation_reason": cancellation_reason, "cancellation_note": cancellation_note}
        Orders.writes.append(status)
        return dict(Orders.row)


@pytest.fixture
def seller(monkeypatch):
    Orders.row = {"id": "o1", "status": "confirmed", "payment_status": "paid", "delivery_method": "pickup", "total_amount": 50000}
    Orders.writes = []
    monkeypatch.setattr(sellers, "DAOOrders", Orders)
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "s")
    monkeypatch.setattr(dao.dao_refunds, "DAORefunds", lambda: type("R", (), {"create_refund_for_order": lambda self, o, r: None})())


def cancel(reason, note=None):
    body = Schema.RequestUpdateOrderStatus(status="cancelled", cancellation_reason=reason, cancellation_note=note)
    try:
        return 200, sellers.update_seller_order_status("o1", body, user={"id": "s"})
    except HTTPException as e:
        return e.status_code, e.detail


@pytest.mark.parametrize("reason", ["seller_reject_out_of_ingredients", "seller_reject_too_busy", "seller_reject_store_closing"])
def test_a41b_listed_reason_saved_as_its_code(seller, reason):   # TC-A41b
    assert cancel(reason)[0] == 200
    assert (Orders.row["cancellation_reason"], Orders.row["cancellation_note"]) == (reason, None)


def test_a41b_other_keeps_the_typed_text_as_a_note(seller):
    assert cancel("seller_reject_other", "  Gas leak in the kitchen  ")[0] == 200
    assert (Orders.row["cancellation_reason"], Orders.row["cancellation_note"]) == ("seller_reject_other", "Gas leak in the kitchen")


@pytest.mark.parametrize("reason, note", [("seller_reject_other", "   "), ("seller_reject_other", None),   # other needs its text
                                          ("Khách đổi ý", None), ("Out of ingredients", None), (None, None),   # not a code
                                          ("seller_timeout", None)])                                          # a system code
def test_a41b_anything_else_is_refused(seller, reason, note):
    assert cancel(reason, note)[0] == 400 and Orders.writes == []


def test_a41b_note_has_a_length_limit():
    with pytest.raises(Exception):
        Schema.RequestUpdateOrderStatus(status="cancelled", cancellation_reason="seller_reject_other", cancellation_note="x" * 301)


def test_a41b_no_rider_cancel_of_a_failed_delivery(seller):
    Orders.row["status"] = "delivery_failed"
    assert cancel("no_driver")[0] == 200 and Orders.row["cancellation_reason"] == "no_driver"


# ── TC-A40b: every code has the buyer's and the seller's words in both languages ────────────────────────────
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"   # CI mounts it at /frontend/src (T172)
CODES = {orders.SELLER_LATE_REASON, orders.DELIVERY_FAILED_REASON, orders.BUYER_CANCELLED_REASON, order_expiry.TIMEOUT_REASON,
         dao_orders.SOLD_OUT_REASON, *sellers.SELLER_CANCEL_REASONS, "admin_cancel"}   # admin_cancel: the admin app writes it


@pytest.mark.parametrize("locale", ["en-PH", "vi"])
def test_a40b_every_code_has_words(locale):
    import json
    reasons = json.loads((FRONTEND / "i18n" / "locales" / f"{locale}.json").read_text(encoding="utf-8"))["cancel_reason"]
    for viewer in ("buyer", "seller"):
        missing = CODES - set(reasons[viewer])
        assert not missing, (viewer, missing)
    assert "{note}" not in reasons["buyer"]["seller_reject_other"]      # a seller's own words never reach the buyer
    assert "{note}" in reasons["seller"]["seller_reject_other"]


# ── QA: the note never reaches the buyer, and the seller gets only its own ─────────────────────────────────────
def test_buyer_reads_never_select_the_note():
    selected = []

    class Query:
        def __getattr__(self, name):
            def call(*args, **kw):
                if name == "select":
                    selected.append(args[0])
                return self
            return call

        def execute(self):
            return type("R", (), {"data": None})()
    dao = dao_orders.DAOOrders.__new__(dao_orders.DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, name: Query()})()
    dao.read_orders_by_user_id("u1")
    dao.read_order_by_id("o1", "u1")
    assert len(selected) == 2 and not [c for c in selected if "cancellation_note" in c]


@pytest.mark.parametrize("reason, shown", [("seller_reject_other", True), ("admin_cancel", False), ("no_driver", False)])
def test_seller_gets_only_its_own_note(monkeypatch, reason, shown):
    row = {"id": "o1", "status": "cancelled", "cancellation_reason": reason, "cancellation_note": "typed words"}
    dao = type("D", (), {"read_order_by_id_for_seller": lambda self, o, s: dict(row), "read_status_history": lambda self, o: [],
                         "read_delivery_history": lambda self, o: []})
    monkeypatch.setattr(sellers, "DAOOrders", dao)
    monkeypatch.setattr(sellers, "_get_seller", lambda user: {"id": "s"})
    monkeypatch.setattr(sellers, "complaints_for_order", lambda order, uid, role: {})
    order = sellers.get_seller_order_detail("o1", user={"id": "u"})["order"]
    assert ("cancellation_note" in order) is shown
