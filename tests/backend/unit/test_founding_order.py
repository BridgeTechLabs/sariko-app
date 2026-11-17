"""Buyer home page order (flow 20261116-seller-order, QĐ-11, TC-18): inside a group the stores follow display_order,
the admin's number, even for an active store without pickup coordinates that the buyer sees as coming soon.
A fake client sorts by the order() calls the DAO makes, as PostgREST does, so ordering by status first would fail here.

Run from tests/backend:  pytest unit/test_founding_order.py
"""
from dao import dao_seller_profiles


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.keys = rows, []

    def select(self, *a):
        return self

    def eq(self, *a):
        return self

    def order(self, column):
        self.keys.append(column)
        return self

    def execute(self):
        data = sorted(self.rows, key=lambda r: tuple(r[k] for k in self.keys))
        return type("R", (), {"data": [dict(r) for r in data]})()


def seller(name, status, order, created, lat=10.7, lon=106.7):
    return {"id": name, "user_id": name, "store_name": name, "slug": name, "avatar_url": None, "status": status,
            "is_open": True, "weekly_hours": None, "lat": lat, "lon": lon, "display_order": order, "created_at": created}


def read(rows):
    dao = dao_seller_profiles.DAOSellerProfiles()
    dao._supabase_client = type("C", (), {"table": lambda self, name: FakeQuery(rows)})()
    return [(s["store_name"], s["status"]) for s in dao.read_founding_sellers()]


def test_tc18_admin_order_holds_inside_the_coming_soon_group():
    rows = [seller("X", "active", 30, "2026-01-01", lat=None, lon=None),   # shown as coming_soon: no pickup point
            seller("Y", "coming_soon", 10, "2026-01-02"), seller("Z", "coming_soon", 20, "2026-01-03"),
            seller("A", "active", 50, "2026-01-04"), seller("B", "active", 40, "2026-01-05")]
    assert read(rows) == [("B", "active"), ("A", "active"), ("Y", "coming_soon"), ("Z", "coming_soon"), ("X", "coming_soon")]


def test_same_number_goes_by_created_at():
    rows = [seller("late", "active", 10, "2026-02-01"), seller("early", "active", 10, "2026-01-01")]
    assert [n for n, _ in read(rows)] == ["early", "late"]
