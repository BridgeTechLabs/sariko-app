"""T181 A28 (docs/dev/20261110-audit-rest): an order nobody paid is cancelled (payment_timeout) unpaid_order_expire_minutes
after its last pay link, or after its creation when it never got one. No DB, no network."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from apis import payments
from services import payment_reconcile, vnpay_query

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)   # 19:00 in Vietnam


def link(minutes_ago):   # payment_create_date: Vietnam wall time, no zone (vnp_CreateDate)
    return (NOW - timedelta(minutes=minutes_ago)).astimezone(vnpay_query.VN_TZ).strftime("%Y%m%d%H%M%S")


def created(minutes_ago):   # orders.created_at: timestamp without time zone holding UTC
    return (NOW - timedelta(minutes=minutes_ago)).replace(tzinfo=None).isoformat()


class Orders:
    def __init__(self, rows):
        self.rows = {r["id"]: {"status": "pending", "payment_status": "pending", **r} for r in rows}
        self.asked_before = None

    def read_expirable_unpaid_orders(self, created_before):
        self.asked_before = created_before
        return [dict(r) for r in self.rows.values()]

    def expire_unpaid_order(self, order_id):   # conditional like the DB: still pending and unpaid
        r = self.rows[order_id]
        if r["status"] != "pending" or r["payment_status"] not in ("pending", "failed"):
            return False
        r.update(status="cancelled", cancellation_reason="payment_timeout")
        return True


@pytest.fixture
def run(monkeypatch):
    def go(rows, minutes=30):
        dao = Orders(rows)
        monkeypatch.setattr(payment_reconcile, "DAOOrders", lambda: dao)
        monkeypatch.setattr(payment_reconcile, "DAOAdminConfig",
                            lambda: type("C", (), {"get_positive_int": lambda self, k, d: minutes if k == "unpaid_order_expire_minutes" else d})())
        n = payment_reconcile.expire_unpaid_orders(NOW)
        return n, {i: r["status"] for i, r in dao.rows.items()}, dao
    return go


def test_a28a_timeout_from_the_last_link_in_vietnam_time(run):   # TC-A28a / A28d
    n, status, dao = run([
        {"id": "late", "created_at": created(90), "payment_create_date": link(31)},
        {"id": "edge", "created_at": created(90), "payment_create_date": link(30)},     # exactly 30:00 -> not yet
        {"id": "relinked", "created_at": created(300), "payment_create_date": link(5)},  # a new link restarts the clock
        {"id": "nolink", "created_at": created(31), "payment_create_date": None},
        {"id": "nolink_new", "created_at": created(10), "payment_create_date": None},
        {"id": "failed_link", "created_at": created(60), "payment_create_date": link(45), "payment_status": "failed"},
    ])
    assert status == {"late": "cancelled", "edge": "pending", "relinked": "pending", "nolink": "cancelled",
                      "nolink_new": "pending", "failed_link": "cancelled"}
    assert n == 3 and dao.rows["late"]["cancellation_reason"] == "payment_timeout"


def test_a28a_setting_moves_the_deadline(run):
    rows = [{"id": "o", "created_at": created(90), "payment_create_date": link(40)}]
    assert run(rows, minutes=30)[1] == {"o": "cancelled"}
    assert run(rows, minutes=60)[1] == {"o": "pending"}


def test_a28_setting_never_cuts_a_link_still_payable(run):   # QA: floor = link lifetime + one VNPay check
    rows = [{"id": "linked", "created_at": created(90), "payment_create_date": link(10)},
            {"id": "nolink", "created_at": created(10), "payment_create_date": None}]
    assert run(rows, minutes=1)[1] == {"linked": "pending", "nolink": "pending"}
    assert run([{"id": "o", "created_at": created(90), "payment_create_date": link(31)}], minutes=1)[1] == {"o": "cancelled"}


def test_a28e_paid_meanwhile_is_left_alone(run):   # TC-A28e (a), A28g: a second run changes nothing
    n, status, dao = run([{"id": "o", "created_at": created(90), "payment_create_date": link(40), "payment_status": "paid"}])
    assert (n, status) == (0, {"o": "pending"})


def test_a28e_no_new_link_for_a_cancelled_order(monkeypatch):   # TC-A28e (c)
    order = {"id": "o", "status": "cancelled", "payment_status": "pending", "total_amount": 50000}
    monkeypatch.setattr(payments, "DAOOrders", lambda: type("D", (), {"read_order_by_id": lambda self, order_id, user_id: dict(order)})())
    with pytest.raises(HTTPException) as e:
        payments.create_vnpay_payment("o", request=None, user={"id": "u"})
    assert e.value.status_code == 409 and e.value.detail["code"] == "order_cancelled"


def test_a28_job_runs_after_the_vnpay_check(monkeypatch):
    calls = []
    monkeypatch.setattr(payment_reconcile, "reconcile_payments", lambda: calls.append("reconcile") or {"asked": 0, "tried": 0, "errors": 0})
    monkeypatch.setattr(payment_reconcile, "expire_unpaid_orders", lambda: calls.append("expire") or 0)
    monkeypatch.setattr(payment_reconcile, "_vnpay_error", None)
    payment_reconcile.reconcile_run()
    assert calls == ["reconcile", "expire"]   # a payment VNPay confirms this run is never expired by it
