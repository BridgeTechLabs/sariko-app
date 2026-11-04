"""Unit tests for POST /api/v6/vat/original (services/vnpay/invoices/client.py + http.py).

Why this matters: the payload is a legal document sent to the tax authority — wrong field
names or amounts as strings get rejected (code 11), and a lost traceId makes support impossible.
"""
import json
from decimal import Decimal

import pytest
import requests
from pydantic import ValidationError

from services.vnpay.invoices import (
    InvoiceHttp, OriginalVatInvoice, OriginalVatInvoiceRequest, TaxType, VatProduct,
    VnpayInvoiceConfig, VnpayInvoiceError, VnpayInvoiceService,
)


class FakeResponse:
    def __init__(self, body=None, status_code=200, text=None):
        self._body = body
        self.status_code = status_code
        self.text = text if text is not None else str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeTokens:
    def __init__(self):
        self.config = VnpayInvoiceConfig(base_url="https://invoice-api.test", client_id="cid", client_secret="cs")
        self.tokens = ["tok-1", "tok-2"]
        self.invalidated = 0

    def get_token(self):
        return self.tokens[0]

    def invalidate(self):
        self.invalidated += 1
        self.tokens.pop(0)


@pytest.fixture
def calls(monkeypatch):
    state = {"responses": [], "calls": []}

    def fake_post(url, data=None, headers=None, timeout=None):
        state["calls"].append({"url": url, "body": json.loads(data), "headers": headers, "timeout": timeout})
        return state["responses"].pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    return state


@pytest.fixture
def tokens():
    return FakeTokens()


@pytest.fixture
def service(tokens):
    return VnpayInvoiceService(InvoiceHttp(tokens))


def _request(**invoice_overrides):
    invoice = dict(
        request_id="order-123",
        invoice_created_date="2026-10-26",
        invoice_symbol="C26TAA",
        payment_method="TM/CK",
        total_amount_without_discount=Decimal("15000"),
        total_amount=Decimal("15000"),
        total_tax_amount=Decimal("1200.50"),
        total_amount_after_tax=Decimal("16200.50"),
        products=[VatProduct(
            ordinal_number=1, name="Phí dịch vụ nền tảng", property=1,
            amount_without_discount=Decimal("15000"), amount=Decimal("15000"),
            tax="8%", tax_amount=Decimal("1200.50"), amount_after_tax=Decimal("16200.50"),
        )],
        tax_types=[TaxType(tax="8%", amount=Decimal("15000"), tax_amount=Decimal("1200.50"))],
        buyer_name="Nguyễn Văn A",
    )
    invoice.update(invoice_overrides)
    return OriginalVatInvoiceRequest(tax_code="0102030405", invoice=OriginalVatInvoice(**invoice))


def _ok(data=None):
    return FakeResponse({"code": "00", "message": "Success", "traceId": "tr-1", "data": data or {
        "requestId": "order-123", "invoiceNumber": 42, "invoiceSymbol": "C26TAA", "invoiceType": "1",
        "invoiceCreatedDate": "2026-10-26", "taxAuthorityCode": "M1-26-ABC", "lookupCode": "LK1",
    }})


def test_posts_camel_case_payload_with_numeric_amounts(service, calls):
    calls["responses"] = [_ok()]
    service.create_vat_original(_request())

    call = calls["calls"][0]
    assert call["url"] == "https://invoice-api.test/api/v6/vat/original"
    assert call["headers"]["Authorization"] == "Bearer tok-1"
    body = call["body"]
    assert body["taxCode"] == "0102030405"
    assert "autoRelease" not in body           # None → left to VNPAY config
    inv = body["invoice"]
    assert inv["requestId"] == "order-123"
    assert inv["currencyUnit"] == "VND"
    assert inv["buyerName"] == "Nguyễn Văn A"
    assert inv["totalAmount"] == 15000 and isinstance(inv["totalAmount"], int)
    assert inv["totalTaxAmount"] == 1200.5
    assert inv["products"][0]["amountAfterTax"] == 16200.5
    assert inv["taxTypes"] == [{"tax": "8%", "amount": 15000, "taxAmount": 1200.5}]
    assert "buyerEmail" not in inv             # unset optional fields are not sent


def test_auto_send_cqt_alias(service, calls):
    calls["responses"] = [_ok()]
    req = _request()
    req.auto_send_cqt = True
    req.auto_release = True
    service.create_vat_original(req)
    body = calls["calls"][0]["body"]
    assert body["autoSendCQT"] is True and body["autoRelease"] is True


def test_returns_invoice_info_with_trace_id(service, calls):
    calls["responses"] = [_ok()]
    res = service.create_vat_original(_request())
    assert res.request_id == "order-123"
    assert res.invoice_number == 42
    assert res.tax_authority_code == "M1-26-ABC"
    assert res.lookup_code == "LK1"
    assert res.trace_id == "tr-1"


def test_accepts_data_as_list(service, calls):
    calls["responses"] = [FakeResponse({"code": "00", "traceId": "tr", "data": [{"requestId": "order-123"}]})]
    res = service.create_vat_original(_request())
    assert res.request_id == "order-123" and res.invoice_number is None


def test_error_code_raises_with_trace_id(service, calls):
    calls["responses"] = [FakeResponse({"code": "11", "message": "invoiceSymbol không hợp lệ", "traceId": "tr-err"},
                                       status_code=400)]
    with pytest.raises(VnpayInvoiceError) as exc:
        service.create_vat_original(_request())
    assert (exc.value.code, exc.value.trace_id, exc.value.http_status) == ("11", "tr-err", 400)


def test_401_retries_once_with_new_token(service, calls, tokens):
    calls["responses"] = [FakeResponse({"code": "401", "message": "Unauthorized"}, status_code=401), _ok()]
    service.create_vat_original(_request())
    assert tokens.invalidated == 1
    assert [c["headers"]["Authorization"] for c in calls["calls"]] == ["Bearer tok-1", "Bearer tok-2"]


def test_5xx_is_not_retried(service, calls):
    """The invoice may already exist — re-sending the same requestId is not safe."""
    calls["responses"] = [FakeResponse(None, status_code=502, text="<html>Bad Gateway</html>")]
    with pytest.raises(VnpayInvoiceError) as exc:
        service.create_vat_original(_request())
    assert exc.value.http_status == 502
    assert len(calls["calls"]) == 1


@pytest.mark.parametrize("tax", ["0%", "5%", "8%", "10%", "KCT", "KKKNT", "KHAC", "KHAC:5.26%", "KHAC:7%"])
def test_valid_tax_rates(tax):
    TaxType(tax=tax, amount=1, tax_amount=0)


@pytest.mark.parametrize("tax", ["8", "7%", "kct", "KHAC:5.263%", "KHAC: 5%"])
def test_invalid_tax_rates(tax):
    with pytest.raises(ValidationError):
        TaxType(tax=tax, amount=1, tax_amount=0)


def test_rejects_long_symbol_and_bad_date():
    with pytest.raises(ValidationError):
        _request(invoice_symbol="C26TAAX")
    with pytest.raises(ValidationError):
        _request(invoice_created_date="26/10/2026")


def test_rejects_unknown_field():
    with pytest.raises(ValidationError):
        _request(buyer_mail="a@b.c")
