"""Unit tests for GET /api/v6/invoices/pdf (services/vnpay/invoices/client.py + http.py).

Why this matters: the PDF is what the buyer downloads — a broken decode or a lost traceId
means a blank/corrupt file and no way to chase it with VNPAY.
"""
import base64

import pytest
import requests

from services.vnpay.invoices import InvoiceHttp, VnpayInvoiceConfig, VnpayInvoiceError, VnpayInvoiceService

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\n%%EOF"


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

    def fake_get(url, params=None, headers=None, timeout=None):
        state["calls"].append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return state["responses"].pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    return state


@pytest.fixture
def tokens():
    return FakeTokens()


@pytest.fixture
def service(tokens):
    return VnpayInvoiceService(InvoiceHttp(tokens))


def _ok(data=base64.b64encode(PDF_BYTES).decode()):
    return FakeResponse({"code": "00", "message": "Success", "traceId": "tr-1", "data": data})


def _get(service):
    return service.get_invoice_pdf("0102030405", "2026-10-26", "order-123")


def test_sends_query_params_and_decodes_pdf(service, calls):
    calls["responses"] = [_ok()]
    assert _get(service) == PDF_BYTES

    call = calls["calls"][0]
    assert call["url"] == "https://invoice-api.test/api/v6/invoices/pdf"
    assert call["params"] == {"taxCode": "0102030405", "invoiceDate": "2026-10-26", "requestId": "order-123"}
    assert call["headers"]["Authorization"] == "Bearer tok-1"


def test_error_code_raises_with_trace_id(service, calls):
    calls["responses"] = [FakeResponse({"code": "99", "message": "Không tìm thấy hóa đơn", "traceId": "tr-err"},
                                       status_code=400)]
    with pytest.raises(VnpayInvoiceError) as exc:
        _get(service)
    assert (exc.value.code, exc.value.trace_id, exc.value.http_status) == ("99", "tr-err", 400)


def test_401_retries_once_with_new_token(service, calls, tokens):
    calls["responses"] = [FakeResponse({"code": "401", "message": "Unauthorized"}, status_code=401), _ok()]
    assert _get(service) == PDF_BYTES
    assert tokens.invalidated == 1
    assert [c["headers"]["Authorization"] for c in calls["calls"]] == ["Bearer tok-1", "Bearer tok-2"]


def test_non_json_body_raises(service, calls):
    calls["responses"] = [FakeResponse(None, status_code=502, text="<html>Bad Gateway</html>")]
    with pytest.raises(VnpayInvoiceError) as exc:
        _get(service)
    assert exc.value.http_status == 502


@pytest.mark.parametrize("invoice_date", ["26/10/2026", "2026-10-26T00:00:00", "20261026"])
def test_rejects_non_iso_invoice_date_without_calling_api(service, calls, invoice_date):
    with pytest.raises(ValueError):
        service.get_invoice_pdf("0102030405", invoice_date, "order-123")
    assert calls["calls"] == []


@pytest.mark.parametrize("data", [None, "", "not base64!!"])
def test_empty_or_invalid_data_raises(service, calls, data):
    calls["responses"] = [_ok(data)]
    with pytest.raises(VnpayInvoiceError) as exc:
        _get(service)
    assert exc.value.trace_id == "tr-1"
