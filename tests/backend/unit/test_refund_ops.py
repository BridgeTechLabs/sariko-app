"""T175 (docs/dev/20261110-refund-ops): a refund that could not be written reaches the team (A2), the buyer's
order detail carries the extra payment's refund (A6), new push texts exist in both languages (A0).
No DB, no network."""
import pytest

import dao.dao_refunds as dao_refunds
from dao.dao_orders import DAOOrders
from services import push_service, zalo

ORDER = {"id": "a805e862-2aae-402d-b018-7777d7b0615f", "payment_status": "paid", "total_amount": 60000,
         "transaction_ref": "TXN-SECRET-REF", "ipn_data": {"vnp_BankCode": "NCB"}}


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(zalo, "send", lambda kind, text: out.append((kind, text)))
    return out


def refunds_failing_with(monkeypatch, error):
    def create_refund(self, **kw):
        raise Exception(error)
    monkeypatch.setattr(dao_refunds.DAORefunds, "__init__", lambda self: None)
    monkeypatch.setattr(dao_refunds.DAORefunds, "create_refund", create_refund)


def test_a2a_refund_not_written_tells_support(monkeypatch, sent):   # TC-A2a
    refunds_failing_with(monkeypatch, "Supabase error - create_refund: connection reset by 10.0.0.5")
    assert dao_refunds.DAORefunds().create_refund_for_order(ORDER, "seller_cancel") is None   # the cancel goes on
    [(kind, text)] = sent
    assert kind == "support" and "A805E862" in text and "Seller cancelled" in text
    assert "10.0.0.5" not in text and "TXN-SECRET-REF" not in text and "NCB" not in text


def test_a2a_refund_already_there_is_not_an_alarm(monkeypatch, sent):
    refunds_failing_with(monkeypatch, 'duplicate key value violates unique constraint "refunds_order_id_key" (23505)')
    assert dao_refunds.DAORefunds().create_refund_for_order(ORDER, "seller_cancel") is None
    assert sent == []


def test_a2a_unpaid_order_needs_no_refund(monkeypatch, sent):
    refunds_failing_with(monkeypatch, "never called")
    assert dao_refunds.DAORefunds().create_refund_for_order({**ORDER, "payment_status": "pending"}, "buyer_cancel") is None
    assert sent == []


def test_a6_buyer_detail_selects_the_extra_payment_refund():   # TC-A6a / A6b: one place (SQL), no refunds rows
    calls = []

    class Query:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a)) or self

        def execute(self):
            return type("R", (), {"data": {"id": "o1"}})()
    dao = DAOOrders.__new__(DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, name: Query()})()
    dao.read_order_by_id("o1", "u1")
    columns = [a[0] for name, a in calls if name == "select"][0]
    assert "duplicate_refund" in [c.strip() for c in columns.split(",")]


@pytest.mark.parametrize("key", ["payment_after_cancel"])
def test_a0_new_push_has_both_languages(key):   # TC-A0
    assert {"en", "vi"} <= set(push_service.MESSAGES[key])
    assert all(len(push_service.MESSAGES[key][lang]) == 2 for lang in ("en", "vi"))
