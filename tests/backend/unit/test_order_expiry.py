"""Confirm timeout: a window (admin_settings) from the latest of payment, opening time, switch-on."""
from datetime import datetime, timedelta, timezone

import pytest

from core.store_hours import confirm_deadline
from services import order_expiry

WINDOW = timedelta(minutes=30)


def at(hhmm, day=12):  # a VN wall-clock time on 2026-10-<day>, given as UTC (VN = UTC+7)
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, 0, 0, tzinfo=timezone.utc) + timedelta(hours=h - 7, minutes=m)


@pytest.mark.parametrize("paid, opens, closes, opened_at, now, expected", [
    (at("12:00"), None, None, None, at("12:10"), at("12:30")),                      # no hours: from payment
    (at("12:00"), "10:00:00", "20:00:00", None, at("12:10"), at("12:30")),          # paid while open
    (at("23:00", 11), "10:00:00", "20:00:00", None, at("10:05"), at("10:30")),      # paid after close: from opening
    (at("12:00"), None, None, at("13:00"), at("13:10"), at("13:30")),               # switched back on later
    (at("12:00"), None, None, at("09:00"), at("12:10"), at("12:30")),               # old switch-on doesn't matter
    (at("17:00"), "18:00:00", "02:00:00", None, at("01:00", 13), at("18:30")),      # overnight hours, after midnight
    (at("03:00"), "08:00:00", "08:00:00", None, at("03:10"), at("03:30")),          # same time = 24h
])
def test_confirm_deadline(paid, opens, closes, opened_at, now, expected):
    assert confirm_deadline(paid, opens, closes, opened_at, now, WINDOW) == expected


class FakeOrders:
    def __init__(self, orders, seller_acted_first=()):
        self.orders, self.seller_acted_first, self.cancelled = orders, set(seller_acted_first), []

    def read_unconfirmed_paid_orders(self, paid_before):
        return [o for o in self.orders if datetime.fromisoformat(o["paid_at"]) <= paid_before]

    def update_order_status(self, order_id, status, reason=None, expected_status=None):
        assert (status, expected_status) == ("cancelled", "pending")
        if order_id in self.seller_acted_first:
            return None
        self.cancelled.append(order_id)
        return {"id": order_id}


class FakeConfig:
    value = 30

    def get_setting(self, key):
        assert key == "order_confirm_minutes"
        return self.value


@pytest.fixture
def config(monkeypatch):
    fake = FakeConfig()
    monkeypatch.setattr(order_expiry, "DAOAdminConfig", lambda: fake)
    return fake


@pytest.mark.parametrize("value, minutes", [
    (45, 45),
    (None, 30),      # row missing
    (0, 30),         # would cancel everything at once
    ("45", 30),      # stored as a JSON string, not a number
    (True, 30),
])
def test_confirm_window_falls_back_on_bad_values(config, value, minutes):
    config.value = value
    assert order_expiry.confirm_window() == timedelta(minutes=minutes)


@pytest.fixture
def refunds(monkeypatch):
    queued = []
    monkeypatch.setattr(order_expiry.DAORefunds, "__init__", lambda self: None)
    monkeypatch.setattr(order_expiry.DAORefunds, "create_refund_for_order",
                        lambda self, order, reason: queued.append((order["id"], reason)))
    return queued


def _order(oid, paid, is_open=True, opens=None, closes=None):
    return {"id": oid, "paid_at": paid.isoformat(), "payment_status": "paid",
            "seller_profiles": {"is_open": is_open, "opening_time": opens, "closing_time": closes, "opened_at": None}}


def test_expiry_cancels_and_refunds_only_timed_out_orders(monkeypatch, config, refunds):
    fake = FakeOrders([
        _order("late", at("11:00")),
        _order("fresh", at("11:45")),                        # 15 min, not yet
        _order("closed", at("11:00"), is_open=False),         # switch off: never times out
        _order("raced", at("11:00")),                         # seller confirmed at the same moment
    ], seller_acted_first={"raced"})
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)

    assert order_expiry.expire_unconfirmed_orders(now=at("12:00")) == 1
    assert fake.cancelled == ["late"]
    assert refunds == [("late", "seller_timeout")]


def test_expiry_uses_the_configured_window(monkeypatch, config, refunds):
    config.value = 90
    fake = FakeOrders([_order("hour_old", at("11:00"))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)

    assert order_expiry.expire_unconfirmed_orders(now=at("12:00")) == 0   # 60 < 90 minutes
    assert order_expiry.expire_unconfirmed_orders(now=at("12:30")) == 1
