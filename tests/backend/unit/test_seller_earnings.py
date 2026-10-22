"""P1-1: seller earnings — per-order split and payout state, exact money (Decimal, int in
JSON), expected payout day = Vietnam day the order became done + payout_delay_days."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token
from core.payout_cycle import cycle_start, expected_payout_date
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
        values = {"seller_order_history_days": 30, "payout_delay_days": 3, **(settings or {})}
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


@pytest.mark.parametrize("delay, want", [(3, "2026-10-24"), (None, "2026-10-24"), (0, "2026-10-21")])
def test_expected_payout_date(earnings, delay, want):  # TC-27
    # 17:30 UTC on 20/10 is 00:30 on 21/10 in Vietnam; a missing setting means 3 days
    res, _ = earnings(orders=[_order(1, status_changed_at="2026-10-20T17:30:00+00:00"),   # 00:30 VN on 21/10
                              _order(2, payout_status="paid_out")], settings={"payout_delay_days": delay})
    first, paid = res.json()["orders"]
    assert first["expected_payout_date"] == want
    assert paid["expected_payout_date"] is None


def test_expected_day_uses_vietnam_date(earnings):  # TC-27: 23:30 VN stays on that VN day
    res, _ = earnings(orders=[_order(1, status_changed_at="2026-10-20T16:30:00+00:00")])
    assert res.json()["orders"][0]["expected_payout_date"] == "2026-10-23"


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


# payout-cycle §6 (TC-33, TC-34): start 28/10 (Wed), cycle 3, delay 2 → payout days 28/10, 31/10, …
@pytest.mark.parametrize("done, want", [
    ("2026-10-26", "2026-10-28"),   # last day of the 28/10 period
    ("2026-10-27", "2026-10-31"),   # first day of the next one
    ("2026-10-23", "2026-10-25"),   # done + delay before the start date: day by day
    ("2026-10-29", "2026-10-31"),   # last day of the 31/10 period
    ("2026-10-30", "2026-11-03"),
])
def test_expected_payout_date_cycle(done, want):  # TC-34
    assert expected_payout_date(date.fromisoformat(done), 2, 3, date(2026, 10, 28)) == date.fromisoformat(want)


@pytest.mark.parametrize("value, want", [(99991231, None), (20261028, date(2026, 10, 28)), (20261399, None)])
def test_cycle_start(value, want):
    assert cycle_start(value) == want


def test_expected_date_cycle_from_settings(earnings):  # TC-34 through the endpoint (17:30 UTC 26/10 = 00:30 VN 27/10)
    res, _ = earnings(orders=[_order(1, status_changed_at="2026-10-26T17:30:00+00:00")],
                      settings={"payout_delay_days": 2, "payout_cycle_days": 3, "payout_cycle_start_date": 20261028})
    assert res.json()["orders"][0]["expected_payout_date"] == "2026-10-31"


@pytest.mark.parametrize("settings", [{}, {"payout_cycle_days": 3, "payout_cycle_start_date": 99991231}])
def test_expected_date_cycle_off(earnings, settings):  # TC-33: off (or keys missing) = done + delay as before
    res, _ = earnings(orders=[_order(1, status_changed_at="2026-10-26T17:30:00+00:00")],
                      settings={"payout_delay_days": 2, **settings})
    assert res.json()["orders"][0]["expected_payout_date"] == "2026-10-29"
