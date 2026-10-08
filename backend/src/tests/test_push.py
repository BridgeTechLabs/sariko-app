"""Web Push routing + endpoint guard. No DB, no network.

Run from backend/src:  python -m pytest tests/test_push.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
