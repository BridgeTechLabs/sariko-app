"""Confirm timeout: a window (admin_settings) from the latest of payment, opening time, switch-on."""
from datetime import datetime, timedelta, timezone

import pytest

from core.store_hours import confirm_deadline
from dao.dao_admin_config import DAOAdminConfig
from services import order_expiry

WINDOW = timedelta(minutes=30)


def at(hhmm, day=12):  # a VN wall-clock time on 2026-10-<day>, given as UTC (VN = UTC+7)
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, 0, 0, tzinfo=timezone.utc) + timedelta(hours=h - 7, minutes=m)


def daily(opens, closes, days=range(1, 8)):  # weekly_hours with the same slot on `days`, the rest off
    return {str(d): ({"open": opens, "close": closes} if d in days else None) for d in range(1, 8)}


# 2026-10-12 is a Monday; 11 = Sunday, 13 = Tuesday
@pytest.mark.parametrize("paid, hours, opened_at, now, expected", [
    (at("12:00"), None, None, at("12:10"), at("12:30")),                                # no hours: from payment
    (at("12:00"), daily("10:00", "20:00"), None, at("12:10"), at("12:30")),             # paid while open
    (at("23:00", 11), daily("10:00", "20:00"), None, at("10:05"), at("10:30")),         # paid after close: from opening
    (at("12:00"), None, at("13:00"), at("13:10"), at("13:30")),                         # switched back on later
    (at("12:00"), None, at("09:00"), at("12:10"), at("12:30")),                         # old switch-on doesn't matter
    (at("17:00"), daily("18:00", "02:00"), None, at("01:00", 13), at("18:30")),         # overnight, after midnight
    (at("21:00", 11), daily("18:00", "02:00", {1}), None, at("01:00", 13), at("18:30")),  # Tuesday off: Monday's slot
    (at("12:00", 11), daily("10:00", "20:00", {2}), None, at("10:05", 13), at("10:30", 13)),  # paid Sunday, Monday off
    (at("03:00"), daily("08:00", "08:00"), None, at("03:10"), at("03:30")),             # same time = whole day
])
def test_confirm_deadline(paid, hours, opened_at, now, expected):
    assert confirm_deadline(paid, hours, opened_at, now, WINDOW) == expected


class FakeOrders:
    def __init__(self, orders, seller_acted_first=()):
        self.orders, self.seller_acted_first, self.cancelled = orders, set(seller_acted_first), []

    def read_unconfirmed_paid_orders(self, paid_before):
        return [o for o in self.orders if datetime.fromisoformat(o["paid_at"]) <= paid_before and o["id"] not in self.cancelled]

    def update_order_status(self, order_id, status, reason=None, expected_status=None):
        assert (status, expected_status) == ("cancelled", "pending")
        if order_id in self.seller_acted_first:
            return None
        self.cancelled.append(order_id)
        return {"id": order_id}


class FakeConfig(DAOAdminConfig):
    """Only the DB read is faked; the real get_minutes validation runs."""
    value = 30
    preorder = 720
    reminder = 10

    def __init__(self):
        pass  # no Supabase client

    def get_setting(self, key):
        return {"order_confirm_minutes": self.value, "preorder_confirm_minutes": self.preorder,
                "order_confirm_reminder_minutes": self.reminder}[key]

    def get_positive_ints(self, defaults):
        return {k: self._positive_int(k, self.get_setting(k), d) for k, d in defaults.items()}


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
def seller_pushes(monkeypatch):
    sent = []
    monkeypatch.setattr(order_expiry.push_service, "notify_seller_order_expired", lambda order: sent.append(order["id"]))
    return sent


@pytest.fixture
def reminders(monkeypatch):
    sent = []
    order_expiry._reminded.clear()
    monkeypatch.setattr(order_expiry.push_service, "notify_seller_order_expiring", lambda order: sent.append(order["id"]))
    monkeypatch.setattr(order_expiry.push_service, "notify_admins",
                        lambda event, url, **f: sent.append((event, url, f["code"], f["minutes"])))
    return sent


@pytest.fixture
def refunds(monkeypatch):
    queued = []
    monkeypatch.setattr(order_expiry.DAORefunds, "__init__", lambda self: None)
    monkeypatch.setattr(order_expiry.DAORefunds, "create_refund_for_order",
                        lambda self, order, reason: queued.append((order["id"], reason)))
    return queued


def _order(oid, paid, is_open=True, hours=None):
    return {"id": oid, "paid_at": paid.isoformat(), "payment_status": "paid",
            "seller_profiles": {"is_open": is_open, "weekly_hours": hours, "opened_at": None}}


def test_expiry_cancels_and_refunds_only_timed_out_orders(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([
        _order("late", at("11:00")),
        _order("fresh", at("11:45")),                        # 15 min, not yet
        _order("closed", at("11:00"), is_open=False),         # switch off: never times out
        _order("day_off", at("11:00"), hours=daily("10:00", "20:00", {2})),  # Monday off: clock paused
        _order("raced", at("11:00")),                         # seller confirmed at the same moment
    ], seller_acted_first={"raced"})
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)

    assert order_expiry.expire_unconfirmed_orders(now=at("12:00")) == 1
    assert fake.cancelled == ["late"]
    assert refunds == [("late", "seller_timeout")]
    assert seller_pushes == ["late"]          # not "raced": the seller acted, nothing to tell them


def test_expiry_uses_the_configured_window(monkeypatch, config, refunds, seller_pushes, reminders):
    config.value = 90
    fake = FakeOrders([_order("hour_old", at("11:00"))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)

    assert order_expiry.expire_unconfirmed_orders(now=at("12:00")) == 0   # 60 < 90 minutes
    assert order_expiry.expire_unconfirmed_orders(now=at("12:30")) == 1


def test_reminds_seller_once_before_auto_cancel(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([
        _order("soon", at("11:40")),                           # deadline 12:10, reminder from 12:00
        _order("early", at("11:55")),                          # deadline 12:25: too early to remind
        _order("closed", at("11:40"), is_open=False),          # clock paused: no reminder either
    ])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)

    soon = ["soon", ("admin_order_expiring", "/orders?open=soon", "soon", 10)]   # admin-push TC-3: same moment
    assert order_expiry.expire_unconfirmed_orders(now=at("12:00")) == 0
    assert reminders == soon
    order_expiry.expire_unconfirmed_orders(now=at("12:01"))
    assert reminders == soon                                   # once only
    assert order_expiry.expire_unconfirmed_orders(now=at("12:10")) == 1
    assert fake.cancelled == ["soon"]
    assert reminders == soon                                   # "early" reminds at 12:25 - 10 min
    order_expiry.expire_unconfirmed_orders(now=at("12:15"))
    assert reminders == soon + ["early", ("admin_order_expiring", "/orders?open=early", "early", 10)]


# ── Pre-orders (docs/dev/20261119-preorder-confirm): preorder_confirm_minutes from payment, open or closed ──

H12 = timedelta(hours=12)


def _preorder(oid, paid, days=3, appointment="auto", is_open=False, hours=None, opened_at=None, items=None):
    order = _order(oid, paid, is_open, hours)
    order["seller_profiles"]["opened_at"] = opened_at.isoformat() if opened_at else None
    order["total_amount"] = 150000
    order["delivery_appointment"] = (paid + timedelta(days=days)).isoformat() if appointment == "auto" else appointment
    order["order_items"] = items if items is not None else [{"food_items": {"preorder_day": days}}]
    return order


def test_tc1_closed_store_preorder_cancels_12h_after_payment(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([_preorder("pre", at("10:00"))])          # switch off
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    assert order_expiry.expire_unconfirmed_orders(now=at("21:59")) == 0
    assert order_expiry.expire_unconfirmed_orders(now=at("22:01")) == 1
    assert fake.cancelled == ["pre"] and refunds == [("pre", "seller_timeout")]


def test_tc2_switch_on_does_not_restart_the_preorder_clock():
    order = _preorder("pre", at("10:00"), is_open=True, opened_at=at("16:00"))
    assert order_expiry.order_deadline(order, order["seller_profiles"], at("17:00"), WINDOW, H12) == at("22:00")


def test_tc4_window_longer_than_the_delivery_time_stops_at_delivery():
    order = _preorder("pre", at("10:00"), days=3)
    assert order_expiry.order_deadline(order, {}, at("11:00"), WINDOW, timedelta(minutes=5000)) == at("10:00", 15)


def test_tc10_preorder_without_delivery_time_does_not_break_the_run(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([_preorder("pre", at("10:00", 11), days=2, appointment=None), _order("late", at("21:00", 11))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    assert order_expiry.expire_unconfirmed_orders(now=at("21:59", 11)) == 1     # same-day one still cancels
    assert fake.cancelled == ["late"]
    assert order_expiry.expire_unconfirmed_orders(now=at("22:01", 11)) == 1
    assert fake.cancelled == ["late", "pre"]


def test_tc11_preorder_window_shorter_than_same_day(monkeypatch, config, refunds, seller_pushes, reminders):
    config.preorder = 15
    now = at("12:00")
    fake = FakeOrders([_preorder("remind", now - timedelta(minutes=6)), _preorder("cancel", now - timedelta(minutes=16))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    assert order_expiry.expire_unconfirmed_orders(now=now) == 1
    assert fake.cancelled == ["cancel"] and refunds == [("cancel", "seller_timeout")]
    assert reminders == ["remind", ("admin_order_expiring", "/orders?open=remind", "remind", 9)]


def test_tc12_closed_store_preorder_reminds_once(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([_preorder("pre", at("10:00"))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    order_expiry.expire_unconfirmed_orders(now=at("21:50"))
    order_expiry.expire_unconfirmed_orders(now=at("21:51"))
    assert reminders == ["pre", ("admin_order_expiring", "/orders?open=pre", "pre", 10)]


def test_tc13_preorder_cancels_and_refunds_once(monkeypatch, config, refunds, seller_pushes, reminders):
    fake = FakeOrders([_preorder("pre", at("10:00")), _preorder("raced", at("10:00"))], seller_acted_first={"raced"})
    amounts = []
    monkeypatch.setattr(order_expiry.DAORefunds, "create_refund_for_order",
                        lambda self, order, reason: amounts.append((order["id"], order["total_amount"])))
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    order_expiry.expire_unconfirmed_orders(now=at("22:01"))
    order_expiry.expire_unconfirmed_orders(now=at("22:02"))
    assert fake.cancelled == ["pre"] and amounts == [("pre", 150000)]


def test_tc14_mixed_cart_is_a_preorder_deleted_dish_is_not():
    mixed = _preorder("mixed", at("10:00"), items=[{"food_items": {"preorder_day": 0}}, {"food_items": {"preorder_day": 1}}])
    assert order_expiry.order_deadline(mixed, {}, at("11:00"), WINDOW, H12) == at("22:00")
    deleted = _preorder("deleted", at("10:00"), items=[{"food_items": None}])
    assert order_expiry.order_deadline(deleted, deleted["seller_profiles"], at("11:00"), WINDOW, H12) is None  # closed: paused
    deleted["seller_profiles"]["is_open"] = True
    assert order_expiry.order_deadline(deleted, deleted["seller_profiles"], at("10:10"), WINDOW, H12) == at("10:30")


def test_tc15_missing_preorder_setting_defaults_to_12_hours(monkeypatch, config, refunds, seller_pushes, reminders):
    config.preorder = None
    assert order_expiry.preorder_window() == H12
    fake = FakeOrders([_preorder("pre", at("10:00"))])
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: fake)
    assert order_expiry.expire_unconfirmed_orders(now=at("21:59")) == 0
    assert order_expiry.expire_unconfirmed_orders(now=at("22:01")) == 1
