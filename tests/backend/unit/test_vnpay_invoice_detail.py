"""Unit tests for GET /api/v6/invoices/{taxCode}/{requestId} (services/vnpay/invoices/client.py + models/responses.py).

Why this matters: the detail is how we check an invoice's status/number after creating it —
a parse failure on a field the doc types differently from the sandbox would hide a signed invoice.
"""
from decimal import Decimal

import pytest
import requests

from services.vnpay.invoices import InvoiceHttp, InvoiceStatus, SignStatus, TvanStatus, VnpayInvoiceConfig, VnpayInvoiceError, VnpayInvoiceService

# Sandbox response, 2026-10-24.
SANDBOX_DATA = {
    "id": 1564456077422157824,
    "requestId": "ztest-0002-20261024",
    "refRequestId": None,
    "lookupCode": "310319951991",
    "invoiceType": "1",
    "invoiceSymbol": "C26TZT",
    "invoiceNumber": 1,
    "invoiceCreatedDate": "2026-10-24",
    "currencyUnit": "VND",
    "currencyExchangeRate": 1,
    "paymentMethod": "TM/CK",
    "relatedInvoiceType": None,
    "relatedInvoiceSymbol": None,
    "relatedInvoiceNumber": None,
    "relatedInvoiceCreatedDate": None,
    "invoiceNote": "Thanh toán cho đơn hàng ORDER-0002",
    "warehouseAddress": None,
    "sellerName": "VNPAY - KIỂM THỬ HĐĐT CÓ MÃ",
    "sellerTaxCode": "0102182292-999",
    "buyerName": "Nguyễn Văn A",
    "buyerTaxCode": "0316970660",
    "buyerAddress": "Số 1, đường Nguyễn Huệ, Phường Bến Nghé, TP.HCM",
    "buyerCustomerCode": "CUS-0001",
    "buyerPhoneNumber": "0901234567",
    "buyerEmail": "jack@sariko.store",
    "buyerFullName": "Công ty TNHH ABC",
    "buyerBankAccountNumber": "0071000123456",
    "buyerBankName": "Vietcombank",
    "buyerFax": None,
    "buyerIdNumber": None,
    "buyerPassportNumber": None,
    "buyerBudgetRelationUnitCode": None,
    "totalAmountWithoutDiscount": 1200000,
    "totalAmount": 1000000,
    "totalTaxAmount": 100000,
    "totalDiscountAmount": 200000,
    "totalAmountAfterTax": 1150000,
    "totalPaymentInWord": "Một triệu một trăm năm mươi nghìn đồng",
    "signStatus": 2,
    "sellerInternalDispatchCommand": None,
    "sellerContractNo": None,
    "sellerContractDay": None,
    "sellerConsigneeName": None,
    "sellerTransformerName": None,
    "sellerTransportation": None,
    "buyerConsigneeName": None,
    "sellerDigitalEconomicContract": None,
    "sellerEconomicContractDay": None,
    "tvanStatus": 5,
    "taxAuthorityCode": "009944C6A94D2E494B8A50101B8DE13864",
    "invoiceStatus": "origin",
    "discount": True,
    "source": "api",
    "receipt": "ORDER-0002",
    "status": "signed",
    "sellerStoreCode": "STORE01",
    "sellerStoreName": "Cửa hàng chính",
    "financialLeasingInvoice": False,
    "branchCode": "HEAD-BRANCH",
    "taxTypes": [{"tax": "10%", "amount": 1000000, "taxAmount": 100000}],
    "products": [{
        "property": 1,
        "ordinalNumber": 1,
        "code": "DV001",
        "name": "Dịch vụ tư vấn thiết kế UI/UX",
        "unit": "Gói",
        "quantity": 1,
        "importedQuantity": None,
        "price": 1200000,
        "discountRate": 16.67,
        "discountAmount": 200000,
        "amount": 1000000,
        "amountWithoutDiscount": 1200000,
        "amountAfterTax": 1100000,
        "tax": "10%",
        "taxAmount": 100000,
        "note": None,
        "specialProduct": None,
    }],
    "extraFields": [],
}


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

    def get_token(self):
        return "tok-1"

    def invalidate(self):
        pass


@pytest.fixture
def calls(monkeypatch):
    state = {"responses": [], "calls": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        state["calls"].append({"url": url, "params": params, "headers": headers})
        return state["responses"].pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    return state


@pytest.fixture
def service():
    return VnpayInvoiceService(InvoiceHttp(FakeTokens()))


def _ok(data=SANDBOX_DATA):
    return FakeResponse({"code": "00", "message": "Success", "traceId": "754616162238917", "data": data})


def test_calls_detail_path_with_tax_code_and_request_id(service, calls):
    calls["responses"] = [_ok()]
    service.get_invoice("0102182292-999", "ztest-0002-20261024")

    call = calls["calls"][0]
    assert call["url"] == "https://invoice-api.test/api/v6/invoices/0102182292-999/ztest-0002-20261024"
    assert call["headers"]["Authorization"] == "Bearer tok-1"


def test_request_id_is_url_encoded(service, calls):
    calls["responses"] = [_ok()]
    service.get_invoice("0102182292-999", "a/b c")
    assert calls["calls"][0]["url"].endswith("/0102182292-999/a%2Fb%20c")


def test_parses_sandbox_response(service, calls):
    calls["responses"] = [_ok()]
    inv = service.get_invoice("0102182292-999", "ztest-0002-20261024")

    assert inv.trace_id == "754616162238917"
    assert (inv.request_id, inv.invoice_symbol, inv.invoice_number) == ("ztest-0002-20261024", "C26TZT", 1)
    assert (inv.invoice_type, inv.invoice_status) == ("1", "origin")
    assert inv.status is InvoiceStatus.SIGNED
    assert inv.tvan_status is TvanStatus.ACCEPTED
    assert inv.lookup_code == "310319951991"
    assert inv.tax_authority_code == "009944C6A94D2E494B8A50101B8DE13864"
    assert inv.total_amount_after_tax == Decimal("1150000")
    assert inv.sign_status is SignStatus.SIGNED

    product = inv.products[0]
    assert product.discount_rate == Decimal("16.67")
    assert product.amount_after_tax == Decimal("1100000")
    assert inv.tax_types[0].tax == "10%"
    assert inv.extra_fields == []


def test_accepts_integer_invoice_type_as_documented(service, calls):
    calls["responses"] = [_ok({**SANDBOX_DATA, "invoiceType": 1, "products": None, "taxTypes": None})]
    inv = service.get_invoice("0102182292-999", "ztest-0002-20261024")
    assert inv.invoice_type == "1"
    assert inv.products is None


def test_sign_status_accepts_string_as_in_webhook_doc(service, calls):
    calls["responses"] = [_ok({**SANDBOX_DATA, "signStatus": "3"})]
    assert service.get_invoice("0102182292-999", "ztest-0002-20261024").sign_status is SignStatus.SIGN_ERROR


def test_error_code_raises_with_trace_id(service, calls):
    calls["responses"] = [FakeResponse({"code": "-1", "message": "Unknown error", "traceId": "tr-err"}, status_code=500)]
    with pytest.raises(VnpayInvoiceError) as exc:
        service.get_invoice("0102182292-999", "missing")
    assert (exc.value.code, exc.value.trace_id, exc.value.http_status) == ("-1", "tr-err", 500)


def test_empty_data_raises(service, calls):
    calls["responses"] = [_ok(None)]
    with pytest.raises(VnpayInvoiceError) as exc:
        service.get_invoice("0102182292-999", "ztest-0002-20261024")
    assert exc.value.trace_id == "754616162238917"
