"""sariko-app T181 A29 (docs/dev/20261110-audit-rest): the buyer's order detail says when a paid order the seller has not
accepted will auto-cancel, and has nothing to say while the store is closed (that clock is paused). No DB."""
from datetime import datetime, timedelta, timezone

import apis.orders as orders


def order(**kw):
    paid = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    return {"seller_id": "s1", "status": "pending", "payment_status": "paid", "paid_at": paid,
            "seller_profiles": {"is_open": True, "weekly_hours": None, "opened_at": None, "store_name": "X"}} | kw


def test_a29a_open_store_gives_the_seller_deadline(monkeypatch):
    monkeypatch.setattr(orders, "confirm_window", lambda: timedelta(minutes=10))
    o = order()
    due = orders.confirm_by(o)
    assert abs((due - datetime.fromisoformat(o["paid_at"])).total_seconds() - 600) < 1
    assert o["seller_profiles"] == {"store_name": "X"}   # the store's hours are not sent on


def test_a29a_closed_store_unpaid_or_moved_on_order_has_no_deadline(monkeypatch):
    monkeypatch.setattr(orders, "confirm_window", lambda: timedelta(minutes=10))
    closed = order()
    closed["seller_profiles"]["is_open"] = False
    assert orders.confirm_by(closed) is None
    assert orders.confirm_by(order(payment_status="pending")) is None
    assert orders.confirm_by(order(status="confirmed")) is None
