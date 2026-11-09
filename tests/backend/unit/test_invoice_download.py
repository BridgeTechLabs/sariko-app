"""services/invoice_service.download_invoice_pdf — reads the invoice row, asks VNPAY for its PDF."""
import pytest

import services.invoice_service as svc


class FakeDAO:
    def __init__(self, row):
        self.row = row

    def read_invoice_by_id(self, invoice_id):
        return self.row


class FakeVnpay:
    def __init__(self):
        self.calls = []

    def get_invoice_pdf(self, tax_code, invoice_date, request_id):
        self.calls.append((tax_code, invoice_date, request_id))
        return b"%PDF"


ISSUED = {"id": "inv-1", "status": "issued", "tax_code": "0101234567",
          "invoice_created_date": "2026-10-26", "request_id": "SARIKO-00000000001"}


def _setup(monkeypatch, row):
    vnpay = FakeVnpay()
    monkeypatch.setattr(svc, "DAOInvoices", lambda: FakeDAO(row))
    monkeypatch.setattr(svc, "get_invoice_service", lambda: vnpay)
    return vnpay


def test_uses_stored_tax_code_date_and_request_id(monkeypatch):
    vnpay = _setup(monkeypatch, ISSUED)

    assert svc.download_invoice_pdf("inv-1") == (b"%PDF", "SARIKO-00000000001.pdf")
    assert vnpay.calls == [("0101234567", "2026-10-26", "SARIKO-00000000001")]


def test_timestamp_date_is_cut_to_day(monkeypatch):
    vnpay = _setup(monkeypatch, {**ISSUED, "invoice_created_date": "2026-10-26T00:00:00"})

    svc.download_invoice_pdf("inv-1")

    assert vnpay.calls[0][1] == "2026-10-26"


def test_missing_invoice(monkeypatch):
    _setup(monkeypatch, None)

    with pytest.raises(svc.InvoiceNotFoundError):
        svc.download_invoice_pdf("inv-1")


@pytest.mark.parametrize("row", [{**ISSUED, "status": "pending"}, {**ISSUED, "invoice_created_date": None}])
def test_not_issued(monkeypatch, row):
    vnpay = _setup(monkeypatch, row)

    with pytest.raises(ValueError):
        svc.download_invoice_pdf("inv-1")
    assert vnpay.calls == []
