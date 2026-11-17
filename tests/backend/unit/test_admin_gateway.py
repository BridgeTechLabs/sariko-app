"""T176 A4 (docs/dev/20261110-admin-cancel-notify): the admin backend tells the app an order was cancelled by an admin;
the app reads the order itself and pushes the buyer and the seller. DAOs and the push sender are faked."""
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import admin_gateway
from services import push_service

OID = "11111111-1111-4111-8111-111111111111"
KEY = "gw_test_key_0123456789"


@pytest.fixture
def gw(monkeypatch):
    """POST the notify endpoint; returns (response, pushes sent as (user, event, url, fields))."""
    state = {"order": {"id": OID, "status": "cancelled", "payment_status": "paid", "user_id": "buyer-1",
                       "seller_user_id": "seller-1"},
             "history": [{"status": "pending"}, {"status": "confirmed"}, {"status": "cancelled"}],
             "deduction": False, "pushes": []}
    monkeypatch.setenv("ADMIN_GATEWAY_API_KEY", KEY)

    class Orders:
        def read_order_by_id_raw(self, order_id):
            return state["order"] if state["order"] and order_id == OID else None

        def read_status_history(self, order_id):
            return state["history"]

    class Payouts:
        def has_deduction_for_order(self, order_id):
            return state["deduction"]

    monkeypatch.setattr(admin_gateway, "DAOOrders", Orders)
    monkeypatch.setattr(admin_gateway, "DAOAdminPayouts", Payouts)
    monkeypatch.setattr(push_service, "_send_async",
                        lambda user_id, event, url, **fields: state["pushes"].append((user_id, event, url, fields)))
    app = FastAPI()
    app.include_router(admin_gateway.router, prefix="/rest/v1")
    client = TestClient(app)

    def call(order_id=OID, headers=None):
        res = client.post(f"/rest/v1/admin-gateway/orders/{order_id}/cancelled-notify",
                          headers={"X-Api-Key": KEY} if headers is None else headers)
        return res, state["pushes"]
    call.state = state
    return call


@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "wrong"}, {"X-Api-Key": ""}, {"Authorization": f"Bearer {KEY}"}])
def test_a4a_bad_or_missing_key_is_401(gw, headers):
    res, pushes = gw(headers=headers)
    assert res.status_code == 401 and pushes == []


@pytest.mark.parametrize("env", [None, ""])
def test_a4a_no_key_set_turns_the_gateway_off(gw, monkeypatch, env, caplog):
    if env is None:
        monkeypatch.delenv("ADMIN_GATEWAY_API_KEY")
    else:
        monkeypatch.setenv("ADMIN_GATEWAY_API_KEY", env)
    with caplog.at_level(logging.DEBUG):
        for headers in ({"X-Api-Key": ""}, {}, {"X-Api-Key": KEY}):
            res, pushes = gw(headers=headers)
            assert res.status_code == 503 and pushes == []
    assert KEY not in caplog.text


def test_a4a_key_compared_in_constant_time(gw, monkeypatch):
    seen = []
    real = admin_gateway.hmac.compare_digest
    monkeypatch.setattr(admin_gateway.hmac, "compare_digest", lambda a, b: seen.append(1) or real(a, b))
    assert gw()[0].status_code == 200 and seen == [1]


def test_a4a_not_in_public_docs():
    app = FastAPI()
    app.include_router(admin_gateway.router, prefix="/rest/v1")
    assert not any("admin-gateway" in p for p in app.openapi()["paths"])


@pytest.mark.parametrize("status, code", [("confirmed", 409), ("done", 409), (None, 404)])
def test_a4b_app_checks_the_order_itself(gw, status, code):
    gw.state["order"] = {**gw.state["order"], "status": status} if status else None
    res, pushes = gw()
    assert res.status_code == code and pushes == []


def test_a4b_bad_order_id_is_422(gw):
    res, pushes = gw(order_id="not-a-uuid")
    assert res.status_code == 422 and pushes == []


@pytest.mark.parametrize("paid, history, deduction, payout, buyer_event, seller_event", [
    ("paid", ["confirmed"], False, "pending", "admin_cancelled_paid", "seller_admin_cancelled"),
    ("paid", ["done"], False, "pending", "admin_cancelled_paid", "seller_admin_cancelled_done"),         # not paid out: no earnings
    ("paid", ["done"], True, "processing", "admin_cancelled_paid", "seller_admin_cancelled_charged"),   # Charge to seller
    ("paid", ["done"], False, "paid_out", "admin_cancelled_paid", "seller_admin_cancelled"),            # Sariko covers: kept
    ("pending", [], False, "pending", "admin_cancelled", None),                                         # seller never saw it
])
def test_a4d_message_by_branch(gw, paid, history, deduction, payout, buyer_event, seller_event):
    gw.state["order"] = {**gw.state["order"], "payment_status": paid, "payout_status": payout}
    gw.state["history"] = [{"status": s} for s in ["pending", *history, "cancelled"]]
    gw.state["deduction"] = deduction
    res, pushes = gw()
    assert res.status_code == 200, res.text
    want = [("buyer-1", buyer_event, f"/orders/{OID}", {"code": "11111111"})]
    if seller_event:
        want.append(("seller-1", seller_event, f"/seller/orders/{OID}", {"code": "11111111"}))
    assert pushes == want


def test_a4c_called_twice_pushes_twice(gw):  # QĐ B: accepted (rare; the admin pressed again)
    gw()
    _, pushes = gw()
    assert len(pushes) == 4


@pytest.mark.parametrize("event", ["admin_cancelled_paid", "admin_cancelled", "seller_admin_cancelled",
                                   "seller_admin_cancelled_done", "seller_admin_cancelled_charged"])
def test_a4d_texts_en_vi(event):
    for lang in ("en", "vi"):
        title, body = push_service._message(event, lang, {"code": "11111111"})
        assert "#11111111" in body and "{" not in title + body
    paid_en = push_service._message("admin_cancelled_paid", "en", {"code": "X"})[1]
    assert "refund" in paid_en and "refund" not in push_service._message("admin_cancelled", "en", {"code": "X"})[1]


def test_send_async_passes_fields(monkeypatch):
    """_send_async(**fields) reaches _deliver so {code} is filled (older callers pass none)."""
    got = []
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", "k")
    monkeypatch.setattr(push_service, "DAOPushSubscriptions",
                        lambda: type("S", (), {"read_subscriptions_by_user_id": lambda self, u: [{"endpoint": "e"}]})())
    monkeypatch.setattr(push_service, "_deliver", lambda u, subs, event, url, fields: got.append(fields))
    monkeypatch.setattr(push_service.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    push_service._send_async("u1", "admin_cancelled", "/orders/x", code="ABC")
    push_service._send_async("u1", "cancelled", "/orders/x")
    assert got == [{"code": "ABC"}, {}]
