"""Countdown under the seller's Accept / Ready buttons (`deadline` on seller orders).
No DB, no network."""
from datetime import datetime, timedelta, timezone

import pytest

import apis.orders as orders
import apis.sellers as sellers


class FakeSettings:
    def get_minutes(self, key, default):
        return timedelta(minutes=default)  # 60 for confirmed


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(sellers, "confirm_window", lambda: timedelta(minutes=30))
    monkeypatch.setattr(orders, "DAOAdminConfig", FakeSettings)


NOW = datetime.now(timezone.utc)
OPEN = {"is_open": True, "opening_time": None, "closing_time": None, "opened_at": None}


def iso(dt):
    return dt.isoformat()


def deadline(order, seller=OPEN):
    value = sellers._with_deadlines([{"payment_status": "paid", "delivery_appointment": None, **order}], seller)[0]["deadline"]
    return datetime.fromisoformat(value) if value else None


def test_pending_counts_to_auto_cancel():
    paid = NOW - timedelta(minutes=10)
    assert deadline({"status": "pending", "paid_at": iso(paid)}) == paid + timedelta(minutes=30)


def test_pending_store_closed_shows_nothing():
    closed = {**OPEN, "is_open": False}
    assert deadline({"status": "pending", "paid_at": iso(NOW)}, closed) is None


def test_pending_unpaid_shows_nothing():
    assert deadline({"status": "pending", "paid_at": None, "payment_status": "pending"}) is None


def test_confirmed_counts_to_buyer_cancel():
    accepted = NOW - timedelta(minutes=15)
    assert deadline({"status": "confirmed", "status_changed_at": iso(accepted)}) == accepted + timedelta(hours=1)


def test_scheduled_confirmed_counts_from_appointment():
    appointment = NOW + timedelta(days=1)
    order = {"status": "confirmed", "status_changed_at": iso(NOW), "delivery_appointment": iso(appointment)}
    assert deadline(order) == appointment + timedelta(hours=1)


def test_other_statuses_show_nothing():
    for status in ("ready", "done", "cancelled", "delivery_failed"):
        assert deadline({"status": status, "status_changed_at": iso(NOW), "paid_at": iso(NOW)}) is None
