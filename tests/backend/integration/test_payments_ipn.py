"""Integration tests for VNPay IPN handler.

IPN = server-to-server callback. This is the ONLY trustworthy source for
"is this order paid?". If this endpoint accepts garbage → free orders for attackers.

Tests use FastAPI TestClient + monkeypatched DAOs (no DB).
"""
import urllib.parse

import pytest


def _build_hash_data(params: dict) -> str:
    filtered = {k: v for k, v in params.items() if v is not None and v != ''}
    sorted_params = sorted(filtered.items())
    return '&'.join(
        f"{urllib.parse.quote_plus(str(k), safe='')}"
        f"={urllib.parse.quote_plus(str(v), safe='')}"
        for k, v in sorted_params
    )


def _make_ipn_params(secret: str, order_id: str, amount_vnd: int, response_code: str = "00"):
    """Build a valid IPN query string params dict + signature."""
    from apis.payments import _hmac_sha512

    order_id_nodash = order_id.replace("-", "")
    txn_ref = f"{order_id_nodash}_120500"

    params = {
        "vnp_Amount": str(amount_vnd * 100),
        "vnp_BankCode": "NCB",
        "vnp_CardType": "ATM",
        "vnp_OrderInfo": f"Thanh toan don hang Sariko {order_id_nodash[:8]}",
        "vnp_PayDate": "20260430120500",
        "vnp_ResponseCode": response_code,
        "vnp_TmnCode": "TEST_TMN",
        "vnp_TransactionNo": "14567890",
        "vnp_TransactionStatus": "00" if response_code == "00" else "01",
        "vnp_TxnRef": txn_ref,
    }
    signature = _hmac_sha512(secret, _build_hash_data(params))
    params["vnp_SecureHash"] = signature
    return params


# ─── Mocks for DAO layer ─────────────────────────────────────────────────────
class _FakeOrderDAO:
    """Stand-in for DAOOrders. Records calls so tests can assert side effects."""

    def __init__(self, order_dict):
        self._order = order_dict
        self.update_payment_status_called = False
        self.update_ipn_data_called = False
        self.last_payment_status = None

    def read_order_by_id_raw(self, order_id):
        if self._order and self._order["id"] == order_id:
            return self._order
        return None

    def update_payment_status(self, order_id, payment_status, transaction_ref):
        self.update_payment_status_called = True
        self.last_payment_status = payment_status
        if self._order:
            self._order["payment_status"] = payment_status

    def update_ipn_data(self, order_id, ipn_data):
        self.update_ipn_data_called = True


class _FakePaymentsDAO:
    def __init__(self):
        self.create_called = False

    def create_payment(self, **kwargs):
        self.create_called = True

    def has_transaction(self, transaction_ref):
        return False


# ─── Tests ───────────────────────────────────────────────────────────────────
def test_ipn_valid_payment_success(fastapi_client, vnp_secret, monkeypatch):
    """Happy path: valid signature + matching amount + pending order →
    update payment_status to 'paid', create payment record, return RspCode 00."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "total_amount": 100000,
        "payment_status": "pending",
        "status": "pending",
    })
    fake_payments = _FakePaymentsDAO()

    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)
    monkeypatch.setattr("apis.payments.DAOPayments", lambda: fake_payments)

    params = _make_ipn_params(vnp_secret, order_id, amount_vnd=100000)
    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    data = res.json()
    assert data["RspCode"] == "00"
    assert data["Message"] == "Confirm Success"
    assert fake_orders.update_payment_status_called is True
    assert fake_orders.last_payment_status == "paid"
    assert fake_payments.create_called is True


def test_ipn_invalid_signature_rejected(fastapi_client, vnp_secret, monkeypatch):
    """Tampered signature → reject with RspCode 97, no DB write."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "total_amount": 100000,
        "payment_status": "pending",
        "status": "pending",
    })
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)

    params = _make_ipn_params(vnp_secret, order_id, amount_vnd=100000)
    params["vnp_SecureHash"] = "0" * 128  # garbage hash, valid length

    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    assert res.json()["RspCode"] == "97"
    assert fake_orders.update_payment_status_called is False, \
        "Must NOT update DB on signature mismatch"


def test_ipn_amount_mismatch_rejected(fastapi_client, vnp_secret, monkeypatch):
    """Order in DB is 100k, IPN claims 1k → reject with RspCode 04."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "total_amount": 100000,  # actual order amount
        "payment_status": "pending",
        "status": "pending",
    })
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)

    # IPN claims paid only 1000 VND
    params = _make_ipn_params(vnp_secret, order_id, amount_vnd=1000)
    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    assert res.json()["RspCode"] == "04"
    assert res.json()["Message"] == "Invalid amount"
    assert fake_orders.update_payment_status_called is False


def test_ipn_idempotent_already_paid(fastapi_client, vnp_secret, monkeypatch):
    """Already-paid order → return 'Order already confirmed', no double payment record."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "total_amount": 100000,
        "payment_status": "paid",  # already paid
    })
    fake_payments = _FakePaymentsDAO()
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)
    monkeypatch.setattr("apis.payments.DAOPayments", lambda: fake_payments)

    params = _make_ipn_params(vnp_secret, order_id, amount_vnd=100000)
    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    assert res.json()["RspCode"] == "02"
    assert fake_payments.create_called is False, \
        "Must NOT create duplicate payment record for already-paid order"


def test_ipn_order_not_found(fastapi_client, vnp_secret, monkeypatch):
    """Unknown order_id → return RspCode 01."""
    fake_orders = _FakeOrderDAO(None)
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)

    nonexistent_id = "ffffffff-ffff-4fff-ffff-ffffffffffff"
    params = _make_ipn_params(vnp_secret, nonexistent_id, amount_vnd=100000)
    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    assert res.json()["RspCode"] == "01"


def test_ipn_failed_payment_logs_attempt_keeps_order_pending(fastapi_client, vnp_secret, monkeypatch):
    """VNPay reports failure (response_code != 00) → ack with RspCode 00 (so VNPay
    stops retrying) AND log a 'failed' payment row for audit. Order.payment_status
    MUST stay 'pending' so the user can retry payment from the order detail page."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "total_amount": 100000,
        "payment_status": "pending",
        "status": "pending",
    })
    fake_payments = _FakePaymentsDAO()
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)
    monkeypatch.setattr("apis.payments.DAOPayments", lambda: fake_payments)

    # response_code "24" = customer cancelled at VNPay
    params = _make_ipn_params(vnp_secret, order_id, amount_vnd=100000, response_code="24")
    res = fastapi_client.get("/payments/vnpay/ipn", params=params)

    assert res.status_code == 200
    assert res.json()["RspCode"] == "00"
    assert fake_orders.update_payment_status_called is False, \
        "Must NOT change order.payment_status — user needs to retry"
    assert fake_orders._order["payment_status"] == "pending"
    assert fake_payments.create_called is True, \
        "Must record the failed attempt for audit trail"


def test_ipn_payment_row_amount_is_order_total_decimal(fastapi_client, vnp_secret, monkeypatch):
    """T89: payments.amount is the order's numeric total_amount as Decimal, to the đồng,
    for a success and a failure (PostgREST returns numeric as "65000.00")."""
    from decimal import Decimal
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    for code, status in (("00", "succeeded"), ("24", "failed")):
        sent = {}
        fake_payments = _FakePaymentsDAO()
        fake_payments.create_payment = lambda **kw: sent.update(kw)
        monkeypatch.setattr("apis.payments.DAOOrders", lambda: _FakeOrderDAO({
            "id": order_id, "total_amount": "65000.00", "payment_status": "pending", "status": "pending"}))
        monkeypatch.setattr("apis.payments.DAOPayments", lambda: fake_payments)

        params = _make_ipn_params(vnp_secret, order_id, amount_vnd=65000, response_code=code)
        assert fastapi_client.get("/payments/vnpay/ipn", params=params).json()["RspCode"] == "00"
        assert sent["status"] == status
        assert sent["amount"] == Decimal("65000.00") and type(sent["amount"]) is Decimal


# ─── Regression baseline R1: unsigned / signed with another secret ──────────


@pytest.mark.parametrize("tamper", ["drop_hash", "other_secret", "empty_query"])
def test_ipn_unsigned_or_foreign_signature_rejected(fastapi_client, vnp_secret, monkeypatch, tamper):
    """No vnp_SecureHash, or a hash made with another merchant's secret → 97, nothing written."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    fake_orders = _FakeOrderDAO({"id": order_id, "total_amount": 100000, "payment_status": "pending", "status": "pending"})
    fake_payments = _FakePaymentsDAO()
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)
    monkeypatch.setattr("apis.payments.DAOPayments", lambda: fake_payments)
    params = _make_ipn_params("another-merchant-secret" if tamper == "other_secret" else vnp_secret, order_id, amount_vnd=100000)
    if tamper == "drop_hash":
        params.pop("vnp_SecureHash")
    res = fastapi_client.get("/payments/vnpay/ipn", params={} if tamper == "empty_query" else params)
    assert res.status_code == 200 and res.json() == {"RspCode": "97", "Message": "Invalid Checksum"}
    assert not fake_orders.update_payment_status_called and not fake_payments.create_called
