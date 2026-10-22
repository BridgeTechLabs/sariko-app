"""Web Push routing + endpoint guard. No DB, no network.

Run from tests/backend:  pytest unit/test_push.py
"""

import json

import pytest
from pydantic import ValidationError

from schemas import Schema
from services import push_service


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(push_service, "_send_async", lambda user_id, event, url: calls.append((user_id, event, url)))
    return calls


def _order(status, payment_status="paid"):
    return {"id": "o1", "user_id": "buyer", "seller_user_id": "seller", "status": status, "payment_status": payment_status}


def test_status_change_goes_to_buyer(sent):
    push_service.notify_order_status(_order("confirmed"))
    assert sent == [("buyer", "confirmed", "/orders/o1")]


def test_delivery_failed_goes_to_both(sent):
    push_service.notify_order_status(_order("delivery_failed"))
    assert sent == [
        ("buyer", "delivery_failed", "/orders/o1"),
        ("seller", "seller_delivery_failed", "/seller/orders/o1"),
    ]


def test_unpaid_or_pending_is_silent(sent):
    push_service.notify_order_status(_order("cancelled", payment_status="pending"))
    push_service.notify_order_status(_order("pending"))
    assert sent == []


def test_new_order_goes_to_seller(sent):
    push_service.notify_new_order(_order("pending"))
    assert sent == [("seller", "new_order", "/seller/orders/o1")]


def test_buyer_cancel_goes_to_seller(sent):
    push_service.notify_buyer_cancelled(_order("cancelled"))
    push_service.notify_buyer_cancelled(_order("cancelled", payment_status="pending"))
    assert sent == [("seller", "seller_buyer_cancelled", "/seller/orders/o1")]


def _sub(endpoint):
    return Schema.RequestCreatePushSubscription(endpoint=endpoint, keys={"p256dh": "k", "auth": "a"})


def test_endpoint_accepts_push_services():
    _sub("https://fcm.googleapis.com/fcm/send/abc")
    _sub("https://web.push.apple.com/QH8x")
    _sub("https://updates.push.services.mozilla.com/wpush/v2/x")


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/fcm/send/abc",       # not https
    "https://169.254.169.254/latest/meta-data",     # SSRF target
    "https://fcm.googleapis.com.evil.com/x",        # suffix trick
    "https://evilpush.apple.com.attacker.io/x",
])
def test_endpoint_rejects_others(endpoint):
    with pytest.raises(ValidationError):
        _sub(endpoint)


def test_seller_delivered_goes_to_seller(sent):
    push_service.notify_seller_delivered(_order("done"))
    assert sent == [("seller", "seller_delivered", "/seller/orders/o1")]


def test_seller_driver_assigned_goes_to_seller(sent):
    push_service.notify_seller_driver_assigned(_order("ready"))
    assert sent == [("seller", "seller_driver_assigned", "/seller/orders/o1")]


# ─── admin-push (docs/dev/admin-push/ TC-2) ──────────────────────────────────
class _Query:
    """Records the PostgREST filters a DAO builds; returns the canned rows."""
    def __init__(self, rows, filters):
        self.rows, self.filters = rows, filters

    def table(self, name):
        return self

    def select(self, cols):
        return self

    def eq(self, col, value):
        self.filters.append((col, value))
        return self

    def execute(self):
        return type("R", (), {"data": self.rows})()


def _dao(rows):
    from dao.dao_push_subscriptions import DAOPushSubscriptions
    dao, filters = DAOPushSubscriptions.__new__(DAOPushSubscriptions), []  # no Supabase client
    dao._supabase_client, dao._table_name = _Query(rows, filters), "push_subscriptions"
    return dao, filters


def test_marketplace_push_reads_marketplace_devices_only():
    dao, filters = _dao([])
    dao.read_subscriptions_by_user_id("u1")
    assert filters == [("user_id", "u1"), ("app", "marketplace")]


def test_admin_push_reads_admin_devices_only():
    dao, filters = _dao([])
    dao.read_admin_subscriptions()
    assert filters == [("app", "admin")]


def test_notify_admins_sends_once_per_admin_with_all_their_devices(monkeypatch):
    subs = [{"user_id": "a1", "endpoint": "e1"}, {"user_id": "a2", "endpoint": "e2"}, {"user_id": "a1", "endpoint": "e3"}]
    monkeypatch.setattr(push_service, "DAOPushSubscriptions", lambda: type("D", (), {"read_admin_subscriptions": lambda self: subs})())
    delivered = []
    monkeypatch.setattr(push_service, "_deliver", lambda uid, s, event, url, f: delivered.append((uid, [x["endpoint"] for x in s], event, url, f)))
    push_service._send_admins("admin_delivery_failed", "/orders?open=o1", {"code": "o1"})
    assert delivered == [
        ("a1", ["e1", "e3"], "admin_delivery_failed", "/orders?open=o1", {"code": "o1"}),
        ("a2", ["e2"], "admin_delivery_failed", "/orders?open=o1", {"code": "o1"}),
    ]


def test_admin_messages_fill_fields_in_the_admins_language():
    assert push_service._message("admin_new_complaint", "en", {"code": "KN000007", "category": "damaged"}) == \
        ("New complaint KN000007", "Damaged or unsafe. Tap to open it.")
    assert push_service._message("admin_new_complaint", "vi", {"code": "KN000007", "category": "damaged"}) == \
        ("Khiếu nại mới KN000007", "Hư hỏng hoặc không an toàn. Nhấn để xem.")
    assert push_service._message("admin_order_expiring", "vi", {"code": "ab12cd34", "minutes": 10}) == \
        ("Đơn #ab12cd34 chưa được nhận", "Còn 10 phút trước khi tự hủy. Hãy gọi người bán.")
    assert push_service._message("admin_delivery_failed", "en", {"code": "ab12cd34"})[0] == "Order #ab12cd34: delivery failed"
    assert push_service._message("confirmed", "en", {}) == push_service.MESSAGES["confirmed"]["en"]


def test_every_complaint_type_has_a_push_label():
    from apis.complaints import CATEGORIES
    assert {c for cats in CATEGORIES.values() for c in cats} == set(push_service.COMPLAINT_CATEGORIES)


def test_deliver_pushes_the_formatted_payload(monkeypatch):
    sent = []
    monkeypatch.setattr(push_service, "DAOPushSubscriptions", lambda: None)
    monkeypatch.setattr(push_service, "DAOUsers", lambda: type("U", (), {"get_users": lambda self, user_id: {"preferred_language": "Tiếng Việt"}})())
    monkeypatch.setattr(push_service, "webpush", lambda **kw: sent.append((kw["subscription_info"]["endpoint"], json.loads(kw["data"]))))
    push_service._deliver("a1", [{"endpoint": "e1", "p256dh": "k", "auth": "a"}], "admin_delivery_failed", "/orders?open=o1", {"code": "o1"})
    assert sent == [("e1", {"title": "Đơn #o1 giao thất bại", "body": "Lalamove không giao được. Nhấn để mở đơn.", "url": "/orders?open=o1"})]
