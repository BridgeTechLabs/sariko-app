"""T136 Zalo ops messages (docs/dev/zalo-alerts): not configured = no HTTP (TC-1), a failing Zalo never fails the IPN
(TC-2), the new-order message and its switch (TC-3), the admin events (TC-4), refunds (TC-5), the DEV prefix (TC-7).
No network: urlopen is faked and the background thread runs inline."""
import json
import logging

import pytest

from dao.dao_orders import DAOOrders
from dao.dao_refunds import DAORefunds
from services import push_service, zalo
from test_daily_portions import ORDER_ID, _Client, make_ipn_params

CHATS = {"ZALO_CHAT_ORDERS": "c-orders", "ZALO_CHAT_SUPPORT": "c-support", "ZALO_CHAT_OPS": "c-ops"}


class _Thread:
    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class _Sent(list):
    fail = None   # an exception urlopen raises


@pytest.fixture
def http(monkeypatch):
    """Configured as PROD; returns the posted messages."""
    sent = _Sent()

    class Res:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true, "result": {}}'

    def urlopen(req, timeout):
        if sent.fail:
            raise sent.fail
        sent.append({"url": req.full_url, "timeout": timeout, **json.loads(req.data)})
        return Res()

    monkeypatch.setattr(zalo.threading, "Thread", _Thread)
    monkeypatch.setattr(zalo.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("ZALO_BOT_TOKEN", "tok")
    for k, v in CHATS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ENV", "prd")
    monkeypatch.setenv("ADMIN_APP_URL", "https://admin.sariko.store")
    return sent


# ─── TC-1 / TC-7 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("unset", ["ZALO_BOT_TOKEN", "ZALO_CHAT_SUPPORT"])
def test_tc1_not_configured_no_http(http, monkeypatch, unset):
    monkeypatch.delenv(unset)
    zalo.send("support", "x")
    zalo.send("ops", "y")
    assert [m["chat_id"] for m in http] == ([] if unset == "ZALO_BOT_TOKEN" else ["c-ops"])


def test_tc7_prefix_outside_prod(http, monkeypatch):
    zalo.send("ops", "a")
    monkeypatch.setenv("ENV", "dev")
    zalo.send("ops", "b")
    assert [m["text"] for m in http] == ["a", "[TEST DEV] b"]
    assert http[0]["url"] == "https://bot-api.zaloplatforms.com/bottok/sendMessage" and http[0]["timeout"] == 10


def test_error_is_one_log_line_without_token(http, caplog):
    import urllib.error
    http.fail = urllib.error.URLError("timed out")
    with caplog.at_level(logging.ERROR):
        zalo.send("ops", "a")
    assert "[Zalo] not sent: URLError" in caplog.text and "tok" not in caplog.text


# ─── TC-2 / TC-3: the paid IPN ───────────────────────────────────────────────
@pytest.fixture
def paid(fastapi_client, vnp_secret, monkeypatch):
    def call(reserve=True, alerts=1, appointment=None):
        client = _Client(reserve)
        client.order.update(total_amount="125000", delivery_appointment=appointment,
                            seller_profiles={"store_name": "TEST Quán Adobo"})
        dao = DAOOrders.__new__(DAOOrders)
        dao._table_name, dao._supabase_client = "orders", client
        monkeypatch.setattr(dao, "_invalidate_cache_for_order", lambda order_id: None, raising=False)
        monkeypatch.setattr("dao.dao_orders._invalidate_seller_orders", lambda seller_id: None)
        monkeypatch.setattr("apis.payments.DAOOrders", lambda: dao)
        monkeypatch.setattr("apis.payments.DAOPayments", lambda: type("P", (), {"create_payment": lambda self, **kw: None})())
        monkeypatch.setattr("dao.dao_orders.push_service.notify_new_order", lambda order: None)
        monkeypatch.setattr("dao.dao_orders.push_service.notify_order_status", lambda order: None)
        monkeypatch.setattr("dao.dao_orders.DAOAdminConfig", lambda: type("C", (), {
            "get_int_in_range": lambda self, key, default, lo, hi: alerts if key == "zalo_new_order_alerts" else default})())
        monkeypatch.setattr(DAORefunds, "__init__", lambda self: None)
        monkeypatch.setattr(DAORefunds, "create_refund", lambda self, **kw: None)
        res = fastapi_client.get("/payments/vnpay/ipn", params=make_ipn_params(vnp_secret, ORDER_ID, 125000))
        return res.json(), client.order
    return call


def test_tc3_new_order_message(http, paid):
    body, order = paid()
    assert body["RspCode"] == "00" and order["payment_status"] == "paid"
    [msg] = http
    assert msg["chat_id"] == "c-orders"
    assert msg["text"] == ("🛒 New order #ABC12345 · TEST Quán Adobo · 125.000 ₫ · Deliver now\n"
                           f"https://admin.sariko.store/orders?open={ORDER_ID}")


def test_tc3_appointment_in_vietnam_time(http, paid):
    paid(appointment="2026-10-28T05:30:00+00:00")
    assert "125.000 ₫ · Scheduled 28/10 12:30\n" in http[0]["text"]


def test_tc3_switch_off_and_sold_out(http, paid):
    paid(alerts=0)
    paid(reserve=False)
    assert http == []


def test_tc2_zalo_down_keeps_the_ipn(http, paid, caplog):
    http.fail = TimeoutError("timed out")
    with caplog.at_level(logging.ERROR):
        body, order = paid()
    assert body["RspCode"] == "00" and order["payment_status"] == "paid"
    assert "[Zalo] not sent: TimeoutError" in caplog.text


# ─── TC-4: notify_admins ─────────────────────────────────────────────────────
def test_tc4_admin_events(http, monkeypatch):
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", None)   # Zalo does not need web push configured
    push_service.notify_admins("admin_new_complaint", "/complaints?open=c1", code="KN-0001", category="missing_item")
    push_service.notify_admins("admin_order_expiring", "/orders?open=o1", code="abc12345", minutes=4)
    push_service.notify_admins("admin_delivery_failed", "/orders?open=o1", code="abc12345")
    push_service.notify_admins("admin_unknown", "/x")
    assert [(m["chat_id"], m["text"]) for m in http] == [
        ("c-support", "📣 New complaint KN-0001 · Missing item\nhttps://admin.sariko.store/complaints?open=c1"),
        ("c-ops", "⏰ Order #ABC12345 not accepted by the seller, auto-cancels in 4 min. Call the seller.\n"
                  "https://admin.sariko.store/orders?open=o1"),
        ("c-ops", "🚚 Order #ABC12345: delivery failed, Lalamove could not deliver it.\nhttps://admin.sariko.store/orders?open=o1"),
    ]


def test_tc4_bad_fields_do_not_raise(http):
    push_service.notify_admins("admin_order_expiring", "/orders?open=o1", code="abc12345")   # no minutes
    assert http == []


# ─── TC-5: refunds ───────────────────────────────────────────────────────────
class _Refunds:
    def __init__(self, fail=None):
        self.fail = fail

    def table(self, name):
        return self

    def insert(self, data):
        self.data = [{"id": "r1", **data}]
        return self

    def execute(self):
        if self.fail:
            raise Exception(self.fail)
        return self


def _refund(client, reason, amount="125000"):
    dao = DAORefunds.__new__(DAORefunds)
    dao._table_name, dao._supabase_client = "refunds", client
    return dao.create_refund(order_id=ORDER_ID, amount=amount, reason=reason, ipn_data={"vnp_TransactionNo": "1"})


@pytest.mark.parametrize("reason, label", list(zalo.REFUND_REASONS.items()))
def test_tc5_refund_message(http, reason, label):
    assert _refund(_Refunds(), reason)["id"] == "r1"
    [msg] = http
    assert msg["chat_id"] == "c-support"
    assert msg["text"] == f"💸 Refund to process · order #ABC12345 · 125.000 ₫ · {label}\nhttps://admin.sariko.store/refunds"


def test_tc5_failed_insert_no_message(http):
    with pytest.raises(Exception):
        _refund(_Refunds(fail='duplicate key value violates unique constraint "refunds_order_id_key"'), "buyer_cancel")
    assert http == []


def test_tc5_ipn_int_amount(http):   # payments._refund_extra_payment passes an int
    _refund(_Refunds(), "duplicate_payment", amount=1250000)
    assert "· 1.250.000 ₫ · Duplicate payment" in http[0]["text"]
