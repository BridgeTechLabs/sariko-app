"""services/invoice_service.py — one paid order → one commission invoice, saved only once VNPAY created it.

Why this matters: a bad order or buyer must stop before VNPAY is called, an order must never get a
second invoice, and a VNPAY failure must leave no invoices row behind.
"""
from unittest.mock import MagicMock

import pytest
import requests

from services import invoice_service
from services.vnpay.invoices import CreateInvoiceResult, VnpayInvoiceError


def order(order_id="o1", payment_status="paid", commission_amount=19000):
    return {"id": order_id, "seller_id": "s1", "payment_status": payment_status,
            "commission_amount": commission_amount, "vat_rate": 0.1, "vat_amount": commission_amount // 10}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SARIKO_TAX_CODE", "0102030405")
    monkeypatch.setenv("SARIKO_INVOICE_SYMBOL", "C26TSA")
    monkeypatch.setenv("VNPAY_CURRENCY_UNIT", "VND")
    orders, invoices, vnpay, onboarding = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    orders.read_order_for_invoice.return_value = order()
    onboarding.get_seller_invoice_info.return_value = {"tax_code": "0312345678", "full_name": "Maria Santos", "residential_address": "12 Nguyễn Huệ, Q1", "phone": "+84901234567", "email": "maria@example.com", "id_type": "cccd", "id_number": "079123456789", "bank_name": "Vietcombank", "bank_account_number": "1234567890", "nationality": "Philippines"}
    invoices.read_invoice_by_order_id.return_value = None
    invoices.next_invoice_no.return_value = 4
    invoices.create_invoice.side_effect = lambda data: {"id": "inv-1", **data}
    invoices.update_pdf_path.side_effect = lambda invoice_id, path: {"id": invoice_id, "pdf_path": path}
    vnpay.get_invoice_pdf.return_value = b"%PDF"
    monkeypatch.setattr(invoice_service, "upload_private", MagicMock())
    monkeypatch.setattr(invoice_service, "DAOOrders", lambda: orders)
    monkeypatch.setattr(invoice_service, "DAOInvoices", lambda: invoices)
    monkeypatch.setattr(invoice_service, "DAOOnboarding", lambda: onboarding)
    monkeypatch.setattr(invoice_service, "get_invoice_service", lambda: vnpay)
    return orders, invoices, vnpay


@pytest.mark.parametrize("invoice_no, request_id", [(4, "SARIKO-00000000004"), (12345678901, "SARIKO-12345678901")])
def test_request_id_for(invoice_no, request_id):
    assert invoice_service.request_id_for(invoice_no) == request_id


@pytest.mark.parametrize("found, message", [
    (None, "not found"),
    (order(payment_status="pending"), "not paid"),
    (order(commission_amount=0), "no commission"),   # e.g. founding tier
])
def test_invalid_order_stops_before_vnpay(env, found, message):
    orders, invoices, vnpay = env
    orders.read_order_for_invoice.return_value = found
    with pytest.raises(ValueError, match=message):
        invoice_service.create_invoice("o1")
    invoices.next_invoice_no.assert_not_called()
    vnpay.create_vat_original.assert_not_called()
    invoices.create_invoice.assert_not_called()


def test_issues_the_invoice_then_saves_it(env):
    orders, invoices, vnpay = env
    vnpay.create_vat_original.side_effect = lambda req: CreateInvoiceResult(
        request_id=req.invoice.request_id, invoice_number=12, lookup_code="LK", trace_id="t1")

    saved = invoice_service.create_invoice("o1")

    orders.read_order_for_invoice.assert_called_once_with("o1")
    request = vnpay.create_vat_original.call_args.args[0]
    assert [p.name[-2:] for p in request.invoice.products] == ["o1"]
    assert request.invoice.buyer_tax_code == "0312345678"
    assert request.invoice.request_id == "SARIKO-00000000004"   # from next_invoice_no, before the row exists
    assert "lookupCode" not in request.to_wire()["invoice"]     # left to VNPAY
    invoices.create_invoice.assert_called_once()
    row = invoices.create_invoice.call_args.args[0]
    assert {k: row[k] for k in ("order_id", "seller_id", "request_id", "status")} == {
        "order_id": "o1", "seller_id": "s1", "request_id": "SARIKO-00000000004", "status": "issued"}
    assert "invoice_no" not in row   # GENERATED ALWAYS: the DB assigns it
    assert row["total_amount_after_tax"] == "20900"
    assert row["invoice_number"] == "12"
    assert row["lookup_code"] == "LK"                            # saved back from VNPAY's answer
    assert set(row["snapshot_data"]) == {"request", "response"}
    assert saved["id"] == "inv-1"


def test_order_with_an_invoice_stops_before_vnpay(env):
    orders, invoices, vnpay = env
    invoices.read_invoice_by_order_id.return_value = {"id": "inv-0", "order_id": "o1"}
    with pytest.raises(ValueError, match="already has an invoice"):
        invoice_service.create_invoice("o1")
    invoices.read_invoice_by_order_id.assert_called_once_with("o1")
    invoices.next_invoice_no.assert_not_called()
    vnpay.create_vat_original.assert_not_called()


def test_invalid_buyer_stops_before_vnpay(env):
    orders, invoices, vnpay = env
    onboarding = invoice_service.DAOOnboarding()
    onboarding.get_seller_invoice_info.return_value = None
    with pytest.raises(ValueError, match="no approved onboarding application"):
        invoice_service.create_invoice("o1")
    onboarding.get_seller_invoice_info.assert_called_once_with("s1")
    vnpay.create_vat_original.assert_not_called()
    invoices.create_invoice.assert_not_called()


@pytest.mark.parametrize("error", [VnpayInvoiceError("13", "Bad symbol", "t1"), requests.Timeout()])
def test_vnpay_failure_saves_nothing_and_logs_the_request_id(env, caplog, error):
    orders, invoices, vnpay = env
    vnpay.create_vat_original.side_effect = error

    with pytest.raises(type(error)):
        invoice_service.create_invoice("o1")

    invoices.create_invoice.assert_not_called()
    assert "order=o1 request_id=SARIKO-00000000004" in caplog.text


def test_save_failure_after_vnpay_created_it_is_logged_for_manual_fix(env, caplog):
    orders, invoices, vnpay = env
    vnpay.create_vat_original.return_value = CreateInvoiceResult(request_id="SARIKO-00000000004", invoice_number=12)
    invoices.create_invoice.side_effect = Exception("duplicate key value violates unique constraint")

    with pytest.raises(Exception, match="duplicate key"):
        invoice_service.create_invoice("o1")

    assert "VNPAY created but saving failed, order=o1 request_id=SARIKO-00000000004 invoice_number=12" in caplog.text


def test_issued_invoice_pdf_is_copied_to_the_private_bucket(env):
    orders, invoices, vnpay = env
    vnpay.create_vat_original.return_value = CreateInvoiceResult(
        request_id="SARIKO-00000000004", invoice_number=12, invoice_created_date="2026-11-07")

    saved = invoice_service.create_invoice("o1")

    vnpay.get_invoice_pdf.assert_called_once_with("0102030405", "2026-11-07", "SARIKO-00000000004")
    invoice_service.upload_private.assert_called_once_with(
        "sariko-private", "invoices/s1/SARIKO-00000000004.pdf", b"%PDF", "application/pdf", upsert=True)
    invoices.update_pdf_path.assert_called_once_with("inv-1", "invoices/s1/SARIKO-00000000004.pdf")
    assert saved["pdf_path"] == "invoices/s1/SARIKO-00000000004.pdf"


@pytest.mark.parametrize("step", ["download", "upload"])
def test_pdf_failure_keeps_the_issued_invoice(env, caplog, step):
    orders, invoices, vnpay = env
    vnpay.create_vat_original.return_value = CreateInvoiceResult(
        request_id="SARIKO-00000000004", invoice_number=12, invoice_created_date="2026-11-07")
    if step == "download":
        vnpay.get_invoice_pdf.side_effect = requests.Timeout()
    else:
        invoice_service.upload_private.side_effect = Exception("storage down")

    saved = invoice_service.create_invoice("o1")

    assert saved["status"] == "issued" and "pdf_path" not in saved
    invoices.update_pdf_path.assert_not_called()
    assert "storing PDF failed, invoice=inv-1 request_id=SARIKO-00000000004" in caplog.text


@pytest.mark.parametrize("commission_amount", [19000, "19000.00", 0.5])
def test_done_order_with_commission_gets_an_invoice(monkeypatch, commission_amount):
    calls = []
    monkeypatch.setattr(invoice_service, "create_invoice", calls.append)
    invoice_service.create_invoice_for_done_order({"id": "o1", "commission_amount": commission_amount})
    assert calls == ["o1"]


@pytest.mark.parametrize("commission_amount", [0, "0.00", None])
def test_done_order_without_commission_is_skipped(monkeypatch, commission_amount):
    calls = []
    monkeypatch.setattr(invoice_service, "create_invoice", calls.append)
    invoice_service.create_invoice_for_done_order({"id": "o1", "commission_amount": commission_amount})
    assert calls == []


@pytest.mark.parametrize("error", [ValueError("Orders not paid"), VnpayInvoiceError("E01", "bad"), requests.Timeout()])
def test_done_order_invoice_errors_are_only_logged(monkeypatch, caplog, error):
    def fail(order_id):
        raise error

    monkeypatch.setattr(invoice_service, "create_invoice", fail)
    invoice_service.create_invoice_for_done_order({"id": "o1", "commission_amount": 19000})
    assert "auto-create failed for done order=o1" in caplog.text
