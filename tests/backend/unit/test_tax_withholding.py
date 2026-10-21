"""tax-withholding (docs/dev/tax-withholding/README.md): the paid hook computes the per-order
withholding without ever failing the payment (TC-5), and the seller earnings show it."""
import logging

from dao.dao_orders import DAOOrders
from test_seller_earnings import _order, earnings  # noqa: F401  (fixture)


class _Client:
    def __init__(self, fail_compute=False):
        self.rpcs, self.fail_compute = [], fail_compute

    def rpc(self, name, params):
        self.rpcs.append((name, params))
        if name == "compute_order_withholding" and self.fail_compute:
            raise RuntimeError("admin_tax_config missing a rate")
        return self

    def execute(self):
        return self


def _dao(client, monkeypatch):
    dao = DAOOrders.__new__(DAOOrders)    # skip __init__: no Supabase client
    dao._supabase_client = client
    monkeypatch.setattr(dao, "_invalidate_cache_for_order", lambda order_id: None, raising=False)
    monkeypatch.setattr(dao, "read_order_by_id_raw", lambda order_id: None, raising=False)
    return dao


def test_paid_computes_withholding(monkeypatch):
    client = _Client()
    assert _dao(client, monkeypatch).update_payment_status("o1", "paid", "TXN") is True
    assert ("compute_order_withholding", {"p_order_id": "o1"}) in client.rpcs


def test_unpaid_does_not_compute(monkeypatch):
    client = _Client()
    _dao(client, monkeypatch).update_payment_status("o1", "pending")
    assert [name for name, _ in client.rpcs] == ["update_order_payment_status"]


def test_tc5_compute_error_keeps_payment(monkeypatch, caplog):
    client = _Client(fail_compute=True)
    with caplog.at_level(logging.ERROR):
        assert _dao(client, monkeypatch).update_payment_status("o1", "paid", "TXN") is True
    assert client.rpcs[0][0] == "update_order_payment_status"
    assert "withholding not computed for order o1" in caplog.text


def test_earnings_show_withholding(earnings):  # noqa: F811
    res, _ = earnings(
        orders=[_order(1, wh_vat_amount="550", wh_pit_amount="275"), _order(2)],
        payouts=[{"id": "p1", "period_start": "2026-10-15", "period_end": "2026-10-15", "order_count": 1,
                  "net_payout": "48235", "withholding_amount": "825.00", "total_deductions": "0",
                  "status": "pending", "paid_at": None}],
    )
    body = res.json()
    first, second = body["orders"]
    assert (first["wh_vat_amount"], first["wh_pit_amount"]) == (550, 275)
    assert (second["wh_vat_amount"], second["wh_pit_amount"]) == (0, 0)      # not computed yet
    assert body["awaiting_total"] == 2 * 49060 - 825
    assert body["payouts"][0]["withholding_amount"] == 825
    assert type(body["payouts"][0]["withholding_amount"]) is int
