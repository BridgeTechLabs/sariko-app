"""P1-1: seller earnings — per-order split and payout state, exact money (Decimal, int in
JSON), expected payout day = the weekly payout day of the order (docs/dev/payout-auto Q1-Q2, Q6)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token
from core.payout_cycle import expected_payout_date
from dao.dao_admin_config import DAOAdminConfig


def _order(i, **over):
    # numeric columns come back from PostgREST as JSON numbers or strings; use strings
    return {"id": f"o{i}", "subtotal": "55000", "commission_amount": "5500.00", "vat_amount": "440",
            "payout_amount": "49060.00", "payout_status": "pending", "payout_hold": False,
            "status_changed_at": "2026-10-20T16:30:00+00:00", **over}


@pytest.fixture
def earnings(monkeypatch):
    """GET /me/earnings with fake DAOs; returns (response, what the DAOs were asked)."""
    def call(orders=(), payouts=(), settings=None, seller_profile=True):
        app = FastAPI()
        app.include_router(sellers.router)
        app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
        monkeypatch.setattr("apis.sellers.DAOSellerProfiles", lambda: type("P", (), {
            "read_seller_profile_by_user_id": lambda self, uid: {"id": "seller-1"} if seller_profile else None})())
        values = {"seller_order_history_days": 30, **(settings or {})}   # payout keys missing = defaults
        monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
        monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, key: values.get(key))
        asked = {}

        class Orders:
            def read_done_orders_for_earnings(self, seller_id, since):
                asked.update(orders_seller=seller_id, since=since)
                return list(orders)

        class Payouts:
            def read_payouts_by_seller_id(self, seller_id, limit):
                asked.update(payouts_seller=seller_id, limit=limit)
                return list(payouts)

        monkeypatch.setattr("apis.sellers.DAOOrders", Orders)
        monkeypatch.setattr("apis.sellers.DAOAdminPayouts", Payouts)
        return TestClient(app).get("/sellers/me/earnings"), asked
    return call


def test_buyer_gets_403(earnings):  # TC-24
    res, _ = earnings(seller_profile=False)
    assert res.status_code == 403


def test_money_exact_and_int(earnings):  # TC-25
    res, _ = earnings(orders=[_order(1), _order(2), _order(3)])
    body = res.json()
    assert body["awaiting_total"] == 147180
    row = body["orders"][0]
    assert (row["subtotal"], row["commission_amount"], row["vat_amount"], row["payout_amount"]) == (55000, 5500, 440, 49060)
    for value in (body["awaiting_total"], row["payout_amount"]):
        assert type(value) is int


def test_states_and_totals(earnings):  # TC-26
    res, asked = earnings(orders=[
        _order(1),
        _order(2, payout_hold=True),
        _order(3, payout_status="processing"),
        _order(4, payout_status="paid_out"),
    ])
    body = res.json()
    assert [o["payout_state"] for o in body["orders"]] == ["pending", "held", "processing", "paid_out"]
    assert body["awaiting_total"] == 2 * 49060        # pending + processing, not held, not paid out
    assert asked["orders_seller"] == "seller-1"
    expected_since = datetime.now(timezone.utc) - timedelta(days=30)
    assert abs((asked["since"] - expected_since).total_seconds()) < 5


def test_done_query_filters():  # TC-26: only done + paid orders of this seller since the cutoff
    from dao.dao_orders import DAOOrders
    calls = []

    class Q:
        data = []

        def __getattr__(self, name):
            def record(*args, **kwargs):
                calls.append((name, args))
                return self
            return record

        def execute(self):
            return self

    dao = DAOOrders.__new__(DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, t: Q()})()
    since = datetime(2026, 9, 20, tzinfo=timezone.utc)
    dao.read_done_orders_for_earnings("seller-1", since)
    for call in [("eq", ("seller_id", "seller-1")), ("eq", ("payment_status", "paid")),
                 ("eq", ("status", "done")), ("gte", ("status_changed_at", since.isoformat()))]:
        assert call in calls


def test_payouts(earnings):  # TC-28
    payouts = [
        {"id": "p2", "period_start": "2026-10-16", "period_end": "2026-10-16", "order_count": 2,
         "net_payout": "98120.00", "total_deductions": "0", "status": "completed", "paid_at": "2026-10-17T03:00:00+00:00"},
        {"id": "p1", "period_start": "2026-10-15", "period_end": "2026-10-15", "order_count": 1,
         "net_payout": "49060", "total_deductions": "1000", "status": "pending", "paid_at": None},
    ]
    res, asked = earnings(payouts=payouts)
    body = res.json()
    assert asked["payouts_seller"] == "seller-1"
    assert [p["id"] for p in body["payouts"]] == ["p2", "p1"]
    assert body["payouts"][0]["net_payout"] == 98120 and body["payouts"][1]["total_deductions"] == 1000
    assert body["received_total"] == 98120          # completed batches only


@pytest.mark.parametrize("value, want", [(0, 0), (30, 30), (7, 7), (31, 3), (-1, 3), ("abc", 3), (None, 3), (True, 3), (2.5, 3)])
def test_get_int_in_range(monkeypatch, value, want):
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, key: value)
    assert DAOAdminConfig().get_int_in_range("payout_delay_days", 3, 0, 30) == want


def test_money_rounds_half_up(earnings):  # TC-25: DB keeps 2 decimals; JSON rounds like the admin screens
    res, _ = earnings(orders=[_order(1, payout_amount="49060.50", vat_amount="440.49")],
                      payouts=[{"id": "p1", "net_payout": "98120.50", "total_deductions": "0.50", "status": "completed"}])
    body = res.json()
    assert body["orders"][0]["payout_amount"] == 49061
    assert body["orders"][0]["vat_amount"] == 440
    assert body["awaiting_total"] == 49061
    assert body["payouts"][0]["net_payout"] == 98121 and body["payouts"][0]["total_deductions"] == 1
    assert body["received_total"] == 98121
    assert body["payouts_limit"] == 12


# payout-auto: weekly periods Mon 00:00 - Sun 23:59 (VN), paid on payout_weekday once the complaint window is over
VN = timezone(timedelta(hours=7))


def _vn(text):
    return datetime.fromisoformat(text).replace(tzinfo=VN)


@pytest.mark.parametrize("done, want", [
    ("2026-10-26 00:00", "2026-11-03"),   # Monday 00:00: first instant of the period
    ("2026-11-01 23:59", "2026-11-03"),   # Sunday 23:59: same period, window ends Mon 23:59 < Tue 08:00
    ("2026-11-02 00:00", "2026-11-10"),   # next Monday: next period
])
def test_tc1_one_week_tuesday(done, want):  # TC-1
    assert expected_payout_date(_vn(done), 1, 2, 8, 24) == date.fromisoformat(want)


@pytest.mark.parametrize("done, want", [
    ("2026-10-26 00:00", "2026-11-10"),   # 2-week periods from Monday 26/10: 26/10 - 08/11, paid Tue 10/11
    ("2026-11-08 23:59", "2026-11-10"),
    ("2026-11-09 00:00", "2026-11-24"),   # 09/11 - 22/11
    ("2026-10-25 12:00", "2026-10-27"),   # before the anchor: 12/10 - 25/10, paid Tue 27/10
])
def test_tc2_two_weeks(done, want):  # TC-2
    assert expected_payout_date(_vn(done), 2, 2, 8, 24) == date.fromisoformat(want)


@pytest.mark.parametrize("done, hour, want", [
    ("2026-11-01 23:00", 8, "2026-11-09"),    # Monday payout 02/11 08:00 is before the window ends (02/11 23:00)
    ("2026-11-01 07:00", 8, "2026-11-02"),    # window ends 02/11 07:00, before 08:00: paid 02/11
    ("2026-11-01 08:30", 8, "2026-11-09"),    # ends 08:30, after the payout is made at 08:00
])
def test_tc3_window_moves_to_next_period(done, hour, want):  # TC-3
    assert expected_payout_date(_vn(done), 1, 1, hour, 24) == date.fromisoformat(want)


@pytest.mark.parametrize("settings, want", [
    ({}, "2026-11-03"),                                            # keys missing: 1 week, Tuesday, 08:00, 24 h
    ({"payout_weekday": 1}, "2026-11-02"),                         # 00:30 VN 27/10 + 24 h < Mon 02/11 08:00
    ({"payout_period_weeks": 2}, "2026-11-10"),
    ({"payout_weekday": 9, "payout_period_weeks": 0}, "2026-11-03"),   # out of range: defaults
])
def test_tc9_endpoint(earnings, settings, want):  # TC-9: 17:30 UTC 26/10 = 00:30 VN 27/10
    res, _ = earnings(orders=[_order(1, status_changed_at="2026-10-26T17:30:00+00:00"),
                              _order(2, payout_status="paid_out"), _order(3, payout_hold=True)], settings=settings)
    first, paid, held = res.json()["orders"]
    assert first["expected_payout_date"] == want
    assert paid["expected_payout_date"] is None and held["expected_payout_date"] is None
    assert "payout_delay_days" not in res.json()


def test_cancelled_payouts_hidden():  # payout-auto D2: a cancelled payout is not shown to the seller
    from dao.dao_admin_payouts import DAOAdminPayouts
    calls = []

    class Q:
        data = []

        def __getattr__(self, name):
            def record(*args, **kwargs):
                calls.append((name, args))
                return self
            return record

        def execute(self):
            return self

    dao = DAOAdminPayouts.__new__(DAOAdminPayouts)
    dao._table_name = "admin_payouts"
    dao._supabase_client = type("C", (), {"table": lambda self, t: Q()})()
    dao.read_payouts_by_seller_id("seller-1", 12)
    assert ("neq", ("status", "cancelled")) in calls and ("eq", ("seller_id", "seller-1")) in calls
