"""VNPay pay flow per the online docs (spec docs/dev/vnpay-doc-align, group B, TC-09..12).
Buyer IP behind nginx, TxnRef carrying vnp_CreateDate, OrderType "other", IPN for an order
that was cancelled while the buyer paid. DAOs faked, no network.

Run from tests/backend:  pytest integration/test_vnpay_doc_align.py
"""
import re
import urllib.parse
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import payments
from core.auth import verify_token
from core.client_ip import client_ip

ORDER_ID = "abc12345-678a-4bcd-9012-345678901234"
HEX = ORDER_ID.replace("-", "")


def _req(peer, **headers):
    return SimpleNamespace(client=SimpleNamespace(host=peer) if peer else None,
                           headers={k.lower().replace("_", "-"): v for k, v in headers.items()})


# TC-09 buyer IP
@pytest.mark.parametrize("peer,headers,expected", [
    ("172.18.0.5", {"x_real_ip": "1.2.3.4", "x_forwarded_for": "1.2.3.4"}, "1.2.3.4"),   # nginx in docker
    ("127.0.0.1", {"x_forwarded_for": "9.9.9.9, 1.2.3.4"}, "1.2.3.4"),                    # our proxy appended the last one
    ("8.8.8.8", {"x_real_ip": "1.2.3.4", "x_forwarded_for": "1.2.3.4"}, "8.8.8.8"),       # direct caller: header ignored
    ("172.18.0.5", {"x_real_ip": "not-an-ip"}, "172.18.0.5"),
    ("testclient", {}, "127.0.0.1"),
])
def test_tc09_client_ip(peer, headers, expected):
    assert client_ip(_req(peer, **headers)) == expected


class FakeOrders:
    order = None
    create_dates = []

    def read_order_by_id(self, order_id, user_id):
        return self.order

    def read_order_by_id_raw(self, order_id):
        return self.order if self.order and self.order["id"] == order_id else None

    def update_payment_create_date(self, order_id, payment_create_date):
        FakeOrders.create_dates.append(payment_create_date)

    def update_payment_status(self, order_id, payment_status, transaction_ref):
        self.order["payment_status"] = payment_status

    def update_ipn_data(self, order_id, ipn_data):
        pass


class FakePayments:
    rows = []

    def create_payment(self, **kw):
        FakePayments.rows.append(kw)


class FakeRefunds:
    rows = []

    def create_refund(self, **kw):
        if any(r["order_id"] == kw["order_id"] for r in FakeRefunds.rows):
            raise Exception('Supabase error - create_refund: duplicate key value violates unique constraint "refunds_order_id_key" (23505)')
        FakeRefunds.rows.append(kw)
        return {"id": f"rf{len(FakeRefunds.rows)}", **kw}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    FakeOrders.order = {"id": ORDER_ID, "total_amount": 100000, "payment_status": "pending", "status": "pending"}
    FakeOrders.create_dates, FakePayments.rows, FakeRefunds.rows = [], [], []
    monkeypatch.setattr(payments, "DAOOrders", FakeOrders)
    monkeypatch.setattr(payments, "DAOPayments", FakePayments)
    monkeypatch.setattr(payments, "DAORefunds", FakeRefunds)


def _client(peer=("testclient", 50000)):
    app = FastAPI()
    app.include_router(payments.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer"}
    return TestClient(app, client=peer)


def _pay_url_params(peer, headers=None):
    r = _client(peer).post(f"/payments/vnpay/create/{ORDER_ID}", headers=headers or {})
    assert r.status_code == 200, r.text
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.json()["payment_url"]).query))


def test_tc09_pay_url_uses_the_buyer_ip_only_from_the_proxy():
    via_proxy = _pay_url_params(("172.18.0.5", 40000), {"X-Real-IP": "1.2.3.4", "X-Forwarded-For": "1.2.3.4"})
    assert via_proxy["vnp_IpAddr"] == "1.2.3.4"
    direct = _pay_url_params(("8.8.8.8", 40000), {"X-Real-IP": "1.2.3.4"})
    assert direct["vnp_IpAddr"] == "8.8.8.8"


# TC-10 TxnRef + OrderType
def test_tc10_txn_ref_carries_the_create_date():
    p = _pay_url_params(("172.18.0.5", 40000), {"X-Real-IP": "1.2.3.4"})
    assert re.fullmatch(rf"{HEX}_\d{{14}}", p["vnp_TxnRef"])
    assert p["vnp_TxnRef"].split("_")[1] == p["vnp_CreateDate"] == FakeOrders.create_dates[-1]
    assert p["vnp_OrderType"] == "other"
    # the URL's own signature still checks out (hash data = the URL-encoded query, B6)
    sig = p.pop("vnp_SecureHash")
    data = "&".join(f"{urllib.parse.quote_plus(k, safe='')}={urllib.parse.quote_plus(v, safe='')}" for k, v in sorted(p.items()))
    assert payments._hmac_sha512(payments.VNPAY_HASH_SECRET, data) == sig


def _ipn(txn_ref, response_code="00", amount=100000):
    params = {
        "vnp_Amount": str(amount * 100), "vnp_BankCode": "NCB", "vnp_CardType": "ATM",
        "vnp_OrderInfo": f"Thanh toan don hang Sariko {HEX[:8]}", "vnp_PayDate": "20261020153512",
        "vnp_ResponseCode": response_code, "vnp_TmnCode": "TEST_TMN", "vnp_TransactionNo": "14567890",
        "vnp_TransactionStatus": "00" if response_code == "00" else "02", "vnp_TxnRef": txn_ref,
    }
    data = "&".join(f"{urllib.parse.quote_plus(k, safe='')}={urllib.parse.quote_plus(v, safe='')}" for k, v in sorted(params.items()))
    params["vnp_SecureHash"] = payments._hmac_sha512(payments.VNPAY_HASH_SECRET, data)
    return _client().get("/payments/vnpay/ipn", params=params).json()


# TC-11 old and new TxnRef both find the order
@pytest.mark.parametrize("txn_ref", [f"{HEX}_20261020153000", f"{HEX}_153000"])
def test_tc11_ipn_finds_the_order(txn_ref):
    assert _ipn(txn_ref)["RspCode"] == "00"
    assert FakeOrders.order["payment_status"] == "paid"
    assert _client().get("/payments/vnpay/return", params={"vnp_TxnRef": txn_ref}).json()["order_id"] == ORDER_ID


# TC-12 IPN after the order was cancelled
def test_tc12_late_payment_on_a_cancelled_order_queues_a_refund(caplog):
    FakeOrders.order["status"] = "cancelled"
    txn_ref = f"{HEX}_20261020153000"
    res = _ipn(txn_ref)
    assert res["RspCode"] == "00"   # handled: VNPay stops retrying (00 / 02 end the flow)
    assert FakeOrders.order["payment_status"] == "pending"   # NOT paid
    [refund] = FakeRefunds.rows
    assert refund["reason"] == "late_payment" and refund["amount"] == 100000
    assert refund["original_txn_ref"] == txn_ref and refund["payment_create_date"] == "20261020153000"
    assert refund["ipn_data"]["vnp_TransactionNo"] == "14567890"
    assert FakePayments.rows[0]["status"] == "succeeded" and FakePayments.rows[0]["amount"] == 100000
    assert "stays unpaid, refund rf1 queued" in caplog.text
    # VNPay retries the same IPN: no second refund, still ended
    assert _ipn(txn_ref)["RspCode"] == "02" and len(FakeRefunds.rows) == 1


def test_tc12_failed_payment_on_a_cancelled_order_queues_nothing():
    FakeOrders.order["status"] = "cancelled"
    assert _ipn(f"{HEX}_20261020153000", response_code="24")["RspCode"] == "00"
    assert FakeRefunds.rows == [] and FakeOrders.order["payment_status"] == "pending"


def test_tc12_old_style_ref_leaves_the_date_to_the_admin():
    FakeOrders.order["status"] = "cancelled"
    _ipn(f"{HEX}_153000")
    assert FakeRefunds.rows[0]["payment_create_date"] is None
