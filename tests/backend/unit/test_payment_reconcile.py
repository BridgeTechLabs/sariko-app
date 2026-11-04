"""T125 (docs/dev/payment-confirm/README.md): VNPay querydr when the IPN is late or lost. TC-4..TC-10 + the
querydr checksum, 94 and the one-asker-at-a-time claim. VNPay, DAOs and push are faked; the paid case runs the
real IPN handling (apis.payments.apply_vnpay_result)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import payments
from core.auth import verify_token
from services import payment_reconcile, vnpay_query

NOW = datetime.now(timezone.utc)   # the create endpoint reads the real clock
OID = "a805e862-2aae-402d-b018-7777d7b0615f"


def link_made(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).astimezone(vnpay_query.VN_TZ).strftime("%Y%m%d%H%M%S")


def answer(txn_ref, code="00", status="00", amount="6000000", sign=True):
    resp = {"vnp_ResponseId": "r1", "vnp_Command": "querydr", "vnp_ResponseCode": code, "vnp_Message": "ok",
            "vnp_TmnCode": vnpay_query.VNPAY_TMN_CODE, "vnp_TxnRef": txn_ref, "vnp_Amount": amount,
            "vnp_BankCode": "NCB", "vnp_PayDate": "20261021145500", "vnp_TransactionNo": "14567890",
            "vnp_TransactionType": "01", "vnp_TransactionStatus": status, "vnp_OrderInfo": "x",
            "vnp_PromotionCode": None, "vnp_PromotionAmount": None}
    if sign:
        resp["vnp_SecureHash"] = vnpay_query._hash(["" if resp[k] is None else str(resp[k]) for k in vnpay_query.RESPONSE_FIELDS])
    return resp


class FakeOrders:
    """One unpaid order; records what the code did to it."""
    def __init__(self, minutes_ago=6, **over):
        self.order = {"id": OID, "user_id": "buyer-1", "seller_user_id": "seller-user-1", "status": "pending",
                      "payment_status": "pending", "total_amount": 60000, "transaction_ref": None,
                      "payment_create_date": link_made(minutes_ago), "vnpay_checked_at": None, "vnpay_check": None,
                      "vnpay_fail_notified_at": None, "refunds": [], "payments": [], **over}
        self.paid, self.saved, self.links, self.claims, self.rows = [], [], [], 0, []

    # reconcile / check
    def read_unpaid_vnpay_orders(self, created_since):
        return [dict(self.order)] if self.order["payment_status"] == "pending" else []

    def read_vnpay_state(self, order_id):
        return dict(self.order) | {"payments": self.order["payments"] + [
            {"transaction_ref": r["transaction_ref"], "status": r["status"]} for r in self.rows]}

    def claim_vnpay_check(self, order_id, now, last_before):
        last = self.order["vnpay_checked_at"]
        if last and datetime.fromisoformat(last) >= last_before:
            return False
        self.claims += 1
        self.order["vnpay_checked_at"] = now.isoformat()
        return True

    def save_vnpay_check(self, order_id, check, checked_at):
        self.saved.append(check)
        self.order.update(vnpay_check=check, vnpay_checked_at=checked_at.isoformat())

    def set_vnpay_fail_notified(self, order_id, at):
        self.order["vnpay_fail_notified_at"] = at.isoformat()

    # IPN handling (apply_vnpay_result) and create
    def read_order_by_id_raw(self, order_id):
        return dict(self.order)

    def read_order_by_id(self, order_id, user_id):
        return dict(self.order)

    def update_payment_status(self, order_id, payment_status, transaction_ref=None):
        self.paid.append((payment_status, transaction_ref))
        self.order.update(payment_status=payment_status, transaction_ref=transaction_ref)

    def update_ipn_data(self, order_id, ipn_data):
        self.order["ipn_data"] = ipn_data

    def update_payment_create_date(self, order_id, payment_create_date):
        self.links.append(payment_create_date)


@pytest.fixture
def env(monkeypatch):
    class E:
        pass
    e = E()
    e.calls, e.answers, e.pushes, e.rows = [], [], [], []
    e.orders = FakeOrders()

    def post(payload):
        e.calls.append(payload)
        if not e.answers:
            raise AssertionError("querydr called")
        return e.answers.pop(0)

    monkeypatch.setattr(vnpay_query, "_post", post)
    monkeypatch.setattr(vnpay_query, "_server_ip", lambda: "203.0.113.5")
    monkeypatch.setattr(payment_reconcile, "DAOOrders", lambda: e.orders)
    monkeypatch.setattr(payments, "DAOOrders", lambda: e.orders)
    monkeypatch.setattr(payments, "DAOPayments", lambda: type("P", (), {
        "create_payment": lambda self, **kw: e.orders.rows.append(kw),
        "has_transaction": lambda self, ref: any(r["transaction_ref"] == ref for r in e.orders.rows)})())
    cfg = type("C", (), {"get_positive_int": lambda self, k, d: d})
    monkeypatch.setattr(payment_reconcile, "DAOAdminConfig", cfg)
    monkeypatch.setattr(payment_reconcile.push_service, "notify_payment_confirmed", lambda o: e.pushes.append("confirmed"))
    monkeypatch.setattr(payment_reconcile.push_service, "notify_payment_failed", lambda o: e.pushes.append("failed"))
    e.txn = f"{OID.replace('-', '')}_{e.orders.order['payment_create_date']}"
    return e


def test_tc4_paid_at_vnpay_goes_through_the_ipn_handling(env):
    env.answers = [answer(env.txn)]
    assert payment_reconcile.reconcile_payments(NOW)["paid"] == 1
    assert env.orders.paid == [("paid", env.txn)]                 # update_payment_status: withholding + seller push
    assert env.orders.rows[0]["status"] == "succeeded" and env.orders.rows[0]["transaction_ref"] == env.txn
    assert env.orders.order["ipn_data"]["source"] == "querydr" and env.pushes == ["confirmed"]
    q = env.calls[0]
    assert (q["vnp_Command"], q["vnp_TxnRef"], q["vnp_TransactionDate"]) == ("querydr", env.txn, env.orders.order["payment_create_date"])


def test_tc5_failed_link_tells_the_buyer_once(env):
    env.orders = FakeOrders(minutes_ago=20)
    env.txn = f"{OID.replace('-', '')}_{env.orders.order['payment_create_date']}"
    env.answers = [answer(env.txn, status="01")]
    payment_reconcile.reconcile_payments(NOW)
    payment_reconcile.reconcile_payments(NOW + timedelta(minutes=2))   # reuses the answer, no second ask
    assert env.pushes == ["failed"] and len(env.calls) == 1
    assert env.orders.order["payment_status"] == "pending" and env.orders.paid == []


def test_not_yet_expired_is_pending(env):
    env.answers = [answer(env.txn, status="01")]
    payment_reconcile.reconcile_payments(NOW)
    assert env.pushes == [] and env.orders.paid == []


def test_tc6_asked_5_minutes_ago_no_call(env):
    env.orders.order.update(vnpay_checked_at=(NOW - timedelta(minutes=5)).isoformat(),
                            vnpay_check={"vnp_TxnRef": env.txn, "vnp_ResponseCode": "00", "vnp_TransactionStatus": "01",
                                         "vnp_TransactionType": "01"})
    payment_reconcile.reconcile_payments(NOW)
    assert env.calls == []


def test_tc7_order_with_a_refund_is_never_asked(env):
    env.orders.order["refunds"] = [{"id": "rf1"}]
    payment_reconcile.reconcile_payments(NOW)
    assert env.calls == []


@pytest.mark.parametrize("minutes_ago", [3, 60 * 25])
def test_outside_the_window_not_asked(env, minutes_ago):
    env.orders = FakeOrders(minutes_ago=minutes_ago)
    payment_reconcile.reconcile_payments(NOW)
    assert env.calls == []


def test_ipn_already_answered_not_asked(env):
    env.orders.order["payments"] = [{"transaction_ref": env.txn, "status": "failed"}]
    payment_reconcile.reconcile_payments(NOW)
    assert env.calls == []


def test_bad_signature_and_94_change_nothing(env):
    env.answers = [answer(env.txn, sign=False) | {"vnp_SecureHash": "0" * 128}]
    payment_reconcile.reconcile_payments(NOW)               # QuerydrSignatureError: logged, skipped
    assert env.orders.paid == []
    env.orders.order["vnpay_checked_at"] = None
    env.answers = [{"vnp_ResponseCode": "94", "vnp_Message": "Request is duplicated"}]
    payment_reconcile.reconcile_payments(NOW)
    assert env.orders.saved == [] and env.orders.paid == []  # 94 is not kept as the answer


def test_amount_mismatch_is_not_paid(env):
    env.answers = [answer(env.txn, amount="100")]
    payment_reconcile.reconcile_payments(NOW)
    assert env.orders.paid == [] and env.pushes == []


def test_one_asker_at_a_time(env):
    env.orders.order["vnpay_checked_at"] = (NOW - timedelta(seconds=10)).isoformat()   # another caller just claimed
    assert vnpay_query.check_order(env.orders.read_vnpay_state(OID), env.orders, NOW) == ("unknown", None)
    assert env.calls == []


# ---- create a new pay link (Q3)
@pytest.fixture
def client(env):
    app = FastAPI()
    app.include_router(payments.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "buyer-1"}
    return TestClient(app)


def test_tc8_previous_link_still_open(env, client):
    env.orders = FakeOrders(minutes_ago=5)
    env.txn = f"{OID.replace('-', '')}_{env.orders.order['payment_create_date']}"
    env.answers = [answer(env.txn, status="01")]
    res = client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "payment_in_progress"
    assert 9 <= res.json()["detail"]["minutes"] <= 16 and env.orders.links == []


def test_tc9_previous_link_was_paid(env, client):
    env.answers = [answer(env.txn)]
    res = client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "order_already_paid"
    assert env.orders.paid == [("paid", env.txn)] and env.orders.links == []


@pytest.mark.parametrize("setup", ["ipn_failed", "querydr_failed"])
def test_tc10_previous_link_failed_new_link(env, client, setup):
    if setup == "ipn_failed":
        env.orders.order["payments"] = [{"transaction_ref": env.txn, "status": "failed"}]
    else:
        env.answers = [answer(env.txn, status="02")]
    res = client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 200 and res.json()["payment_url"] and len(env.orders.links) == 1


def signed_return(txn_ref, code="24", amount="6000000", good=True):
    params = {"vnp_Amount": amount, "vnp_BankCode": "NCB", "vnp_ResponseCode": code, "vnp_TmnCode": "TEST_TMN",
              "vnp_TransactionNo": "0", "vnp_TransactionStatus": "02", "vnp_TxnRef": txn_ref}
    data = "&".join(f"{k}={v}" for k, v in sorted(params.items()))   # no characters that need encoding
    return params | {"vnp_SecureHash": payments._hmac_sha512(payments.VNPAY_HASH_SECRET, data) if good else "0" * 128}


def test_cancelled_at_vnpay_then_pay_again_at_once(env, client):
    """Signed Return 24 (buyer cancelled at VNPay) = the link's failed result: a new link straight away,
    no querydr (it would say 91 / not found and block for 15 minutes)."""
    env.orders = FakeOrders(minutes_ago=1)
    env.txn = f"{OID.replace('-', '')}_{env.orders.order['payment_create_date']}"
    for _ in range(2):   # F5 on the result page: one failed row only
        res = client.get("/payments/vnpay/return", params=signed_return(env.txn))
        assert res.json()["is_valid"] is True and res.json()["success"] is False
    assert [(r["status"], r["transaction_ref"]) for r in env.orders.rows] == [("failed", env.txn)]
    assert env.orders.order["ipn_data"]["source"] == "return" and env.orders.paid == []
    res = client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 200 and len(env.orders.links) == 1 and env.calls == []


@pytest.mark.parametrize("code", ["07", "99", "42"])
def test_return_or_ipn_with_money_maybe_taken_records_nothing(env, client, code):
    """07 = charged, flagged as suspicious; 99 = other error; unknown code: not a "not paid" (VNPay online
    docs): no failed row, so no new link until VNPay (querydr) settles it."""
    env.orders = FakeOrders(minutes_ago=1)
    env.txn = f"{OID.replace('-', '')}_{env.orders.order['payment_create_date']}"
    assert client.get("/payments/vnpay/return", params=signed_return(env.txn, code=code)).json()["not_charged"] is False
    ipn = payments.apply_vnpay_result({k: v for k, v in signed_return(env.txn, code=code).items() if k != "vnp_SecureHash"})
    assert ipn.status_code == 200 and b'"RspCode":"00"' in ipn.body          # VNPay is acked, stops retrying
    assert env.orders.rows == [] and "ipn_data" not in env.orders.order
    env.answers = [answer(env.txn, status="07")]
    res = client.post(f"/payments/vnpay/create/{OID}")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "payment_in_progress" and env.orders.links == []


@pytest.mark.parametrize("code", sorted(payments.NOT_CHARGED_CODES))
def test_not_charged_codes_record_failed(env, client, code):
    assert client.get("/payments/vnpay/return", params=signed_return(env.txn, code=code)).json()["not_charged"] is True
    assert [r["status"] for r in env.orders.rows] == ["failed"]


def test_unsigned_return_records_nothing(env, client):
    client.get("/payments/vnpay/return", params=signed_return(env.txn, good=False))
    assert env.orders.rows == [] and "ipn_data" not in env.orders.order


def test_signed_return_00_never_marks_paid(env, client):
    res = client.get("/payments/vnpay/return", params=signed_return(env.txn, code="00"))
    assert res.json()["success"] is True and env.orders.paid == [] and env.orders.rows == []


def test_first_link_asks_nothing(env, client):
    env.orders.order["payment_create_date"] = None
    assert client.post(f"/payments/vnpay/create/{OID}").status_code == 200 and env.calls == []


def test_classify_codes():
    made = NOW - timedelta(minutes=20)
    base = {"vnp_ResponseCode": "00", "vnp_TransactionType": "01", "vnp_Amount": "6000000"}
    assert vnpay_query.classify(base | {"vnp_TransactionStatus": "00"}, 60000, made, NOW) == "paid"
    assert vnpay_query.classify(base | {"vnp_TransactionStatus": "04"}, 60000, made, NOW) == "failed"
    assert vnpay_query.classify(base | {"vnp_TransactionStatus": "07"}, 60000, made, NOW) == "unknown"
    assert vnpay_query.classify({"vnp_ResponseCode": "91"}, 60000, made, NOW) == "failed"
    assert vnpay_query.classify({"vnp_ResponseCode": "91"}, 60000, NOW - timedelta(minutes=3), NOW) == "pending"
    assert vnpay_query.classify({"vnp_ResponseCode": "99"}, 60000, made, NOW) == "unknown"
