"""Integration tests for POST /admin/invoices — route → services/invoice_service.create_invoices."""
import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.vnpay.invoices import VnpayInvoiceError

ADMIN_KEY = "test-admin-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("core.auth.ADMIN_API_KEY", ADMIN_KEY)
    from apis import admin

    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app)


def _post(client, order_ids, key=ADMIN_KEY):
    return client.post("/admin/invoices", json={"order_ids": order_ids}, headers={"X-Api-Key": key})


def _service(monkeypatch, result=None, error=None):
    calls = []

    def fake_create_invoices(order_ids):
        calls.append(order_ids)
        if error:
            raise error
        return result

    monkeypatch.setattr("apis.admin.invoices.create_invoices", fake_create_invoices)
    return calls


def test_wrong_api_key_is_forbidden(client, monkeypatch):
    calls = _service(monkeypatch, result={})

    res = _post(client, ["o1"], key="wrong")

    assert res.status_code == 403
    assert calls == []


def test_returns_saved_invoice(client, monkeypatch):
    invoice = {"id": "inv-1", "status": "issued", "request_id": "SARIKO-00000000001"}
    calls = _service(monkeypatch, result=invoice)

    res = _post(client, ["o1", "o2"])

    assert res.status_code == 200
    assert res.json() == {"success": True, "invoice": invoice}
    assert calls == [["o1", "o2"]]


def test_invalid_orders_are_400(client, monkeypatch):
    _service(monkeypatch, error=ValueError("Orders not paid: ['o1']"))

    res = _post(client, ["o1"])

    assert res.status_code == 400
    assert res.json()["detail"] == "Orders not paid: ['o1']"


def test_vnpay_rejection_is_502(client, monkeypatch):
    _service(monkeypatch, error=VnpayInvoiceError("E01", "Invalid buyerTaxCode", trace_id="t-1"))

    res = _post(client, ["o1"])

    assert res.status_code == 502
    assert "[E01] Invalid buyerTaxCode" in res.json()["detail"]


def test_vnpay_timeout_is_504(client, monkeypatch):
    _service(monkeypatch, error=requests.Timeout())

    res = _post(client, ["o1"])

    assert res.status_code == 504
    assert "pending" in res.json()["detail"]
