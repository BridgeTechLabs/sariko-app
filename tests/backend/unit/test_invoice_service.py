"""services/invoice_service.py — several paid orders of one seller → one commission invoice.

Why this matters: all or nothing — a bad order must stop the invoice before anything is saved,
and a VNPAY rejection must free the orders so they can be invoiced again.
"""
from unittest.mock import MagicMock

import pytest
import requests

from services import invoice_service
from services.vnpay.invoices import CreateInvoiceResult, VnpayInvoiceError


def order(order_id, seller_id="s1", payment_status="paid", commission_amount=19000):
    return {"id": order_id, "seller_id": seller_id, "payment_status": payment_status,
            "commission_amount": commission_amount, "vat_rate": 0.1, "vat_amount": commission_amount // 10}


def statuses(invoices):
    """Statuses written to the invoice row, in order (the insert first)."""
    inserted = invoices.create_invoice.call_args.args[0]["status"]
    return [inserted] + [c.args[1]["status"] for c in invoices.update_invoice.call_args_list if "status" in c.args[1]]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SARIKO_TAX_CODE", "0102030405")
    monkeypatch.setenv("SARIKO_INVOICE_SYMBOL", "C26TSA")
    monkeypatch.setenv("VNPAY_CURRENCY_UNIT", "VND")
    orders, invoices, vnpay, onboarding = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    onboarding.get_seller_invoice_info.return_value = {"tax_code": "0312345678", "first_name": "Maria", "last_name": "Santos", "residential_address": "12 Nguyễn Huệ, Q1", "phone": "+84901234567", "email": "maria@example.com", "id_type": "cccd", "id_number": "079123456789", "bank_name": "Vietcombank", "bank_account_number": "1234567890", "nationality": "Philippines"}
    invoices.create_invoice.return_value = {"id": "inv-1", "request_id": "SARIKO-00000000004"}
    invoices.update_invoice.side_effect = lambda invoice_id, data: {"id": invoice_id, **data}
    monkeypatch.setattr(invoice_service, "DAOOrders", lambda: orders)
    monkeypatch.setattr(invoice_service, "DAOInvoices", lambda: invoices)
    monkeypatch.setattr(invoice_service, "DAOOnboarding", lambda: onboarding)
    monkeypatch.setattr(invoice_service, "get_invoice_service", lambda: vnpay)
    return orders, invoices, vnpay


@pytest.mark.parametrize("found, message", [
    ([order("o1")], "not found"),
    ([order("o1"), order("o2", payment_status="pending")], "not paid"),
    ([order("o1"), order("o2", commission_amount=0)], "without commission"),   # e.g. founding tier
    ([order("o1"), order("o2", seller_id="s2")], "more than one seller"),
])
def test_invalid_orders_stop_before_saving(env, found, message):
    orders, invoices, vnpay = env
    orders.read_orders_for_invoice.return_value = found
    with pytest.raises(ValueError, match=message):
        invoice_service.create_invoices(["o1", "o2"])
    invoices.create_invoice.assert_not_called()
    vnpay.create_vat_original.assert_not_called()


def test_issues_one_invoice_for_all_orders(env):
    orders, invoices, vnpay = env
    orders.read_orders_for_invoice.return_value = [order("o2"), order("o1")]
    vnpay.create_vat_original.side_effect = lambda req: CreateInvoiceResult(
        request_id=req.invoice.request_id, invoice_number=12, lookup_code="LK", trace_id="t1")

    saved = invoice_service.create_invoices(["o1", "o2", "o1"])

    request = vnpay.create_vat_original.call_args.args[0]
    assert [p.name[-2:] for p in request.invoice.products] == ["o1", "o2"]   # caller's order, deduped
    assert request.invoice.buyer_tax_code == "0312345678"
    assert request.invoice.request_id == "SARIKO-00000000004"   # from the DB-filled row
    assert "request_id" not in invoices.create_invoice.call_args.args[0]
    assert invoices.create_invoice.call_args.args[0]["seller_id"] == "s1"
    assert invoices.update_invoice.call_args_list[0].args[1]["total_amount_after_tax"] == "41800"
    invoices.create_invoice_orders.assert_called_once_with("inv-1", ["o1", "o2"])
    assert saved["status"] == "issued"
    assert statuses(invoices) == ["initial", "pending", "issued"]
    assert saved["invoice_number"] == "12"
    assert "lookupCode" not in request.to_wire()["invoice"]   # left to VNPAY
    assert saved["lookup_code"] == "LK"                        # saved back from VNPAY's answer


def test_invalid_buyer_stops_before_saving(env):
    orders, invoices, vnpay = env
    orders.read_orders_for_invoice.return_value = [order("o1")]
    onboarding = invoice_service.DAOOnboarding()
    onboarding.get_seller_invoice_info.return_value = None
    with pytest.raises(ValueError, match="no approved onboarding application"):
        invoice_service.create_invoices(["o1"])
    onboarding.get_seller_invoice_info.assert_called_once_with("s1")
    invoices.create_invoice.assert_not_called()
    vnpay.create_vat_original.assert_not_called()


def test_vnpay_rejection_fails_invoice_and_frees_orders(env):
    orders, invoices, vnpay = env
    orders.read_orders_for_invoice.return_value = [order("o1")]
    vnpay.create_vat_original.side_effect = VnpayInvoiceError("13", "Bad symbol", "t1")

    with pytest.raises(VnpayInvoiceError):
        invoice_service.create_invoices(["o1"])

    assert statuses(invoices) == ["initial", "pending", "failed"]
    invoices.deactivate_invoice_orders.assert_called_once_with("inv-1")


def test_timeout_keeps_invoice_pending(env):
    orders, invoices, vnpay = env
    orders.read_orders_for_invoice.return_value = [order("o1")]
    vnpay.create_vat_original.side_effect = requests.Timeout()

    with pytest.raises(requests.Timeout):
        invoice_service.create_invoices(["o1"])

    assert statuses(invoices) == ["initial", "pending"]   # outcome unknown: stays pending
    invoices.deactivate_invoice_orders.assert_not_called()
