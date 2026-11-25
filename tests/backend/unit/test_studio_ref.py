"""AI Studio post -> order (docs/dev/20261123-studio-integration QĐ-1, QĐ-2): create_order keeps a valid ref of the
cart's store within attribution_window_days and drops anything else silently; GET /studio/ref-stats counts paid,
not cancelled orders per ref behind X-Studio-Key. No DB, no network."""
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import apis.orders as orders
import apis.studio as studio

DAY_MS = 86_400_000
orders_db = []   # rows DAOOrders.create_order inserted


class FakeCartItems:
    def read_cart_items_by_user_id(self, user_id):
        return {"id": "cart", "seller_id": "seller", "cart_items": [
            {"id": "ci", "quantity": 2, "food_items": {"id": "f", "name": "Adobo", "seller_id": "seller", "price": 50000,
                                                        "is_available": True, "preorder_day": 0},
             "food_item_variants": None}]}


class FakeOrders:
    def read_orders_by_user_id(self, user_id):
        return orders_db

    def create_order(self, **kw):
        row = {"id": f"o{len(orders_db)}", "status": "pending", "created_at": datetime.utcnow().isoformat(), **kw}
        orders_db.append(row)
        return row


class FakeSellers:
    def read_seller_order_info(self, seller_id):
        return {"user_id": "seller-user", "slug": "nora", "is_open": True, "commission_rate": Decimal("0.1"),
                "address": "Q1", "lat": 10.77, "lon": 106.70, "store_name": "Nora", "phone": "0901234567"}


class FakeConfig:
    def get_tax_rate(self, _):
        return Decimal("0.1")

    def get_positive_int(self, key, default):
        return default


class Noop:
    def create_order_items_from_cart(self, **kw):
        pass

    def delete_cart(self, **kw):
        pass


@pytest.fixture
def client(api, monkeypatch):
    orders_db.clear()
    for name, fake in [("DAOCartItems", FakeCartItems), ("DAOOrders", FakeOrders), ("DAOSellerProfiles", FakeSellers),
                       ("DAOAdminConfig", FakeConfig), ("DAOOrderItems", Noop), ("DAOCarts", Noop)]:
        monkeypatch.setattr(orders, name, fake)
    return api(orders.router)


def place(client, **ref):
    return client.post("/orders", json={"delivery_method": "pickup", **ref})


def now_ms():
    return int(time.time() * 1000)


def good_ref(**change):
    return {"ref_code": "Ab3_x-9", "ref_source": "fb", "ref_slug": "nora", "ref_at": now_ms() - DAY_MS} | change


def test_tc1_valid_ref_is_stored(client):
    res = place(client, **good_ref())
    assert res.status_code == 200, res.text
    assert orders_db[0]["ref_code"] == "Ab3_x-9" and orders_db[0]["ref_source"] == "fb"


def test_tc1_ref_without_source(client):
    assert place(client, **good_ref(ref_source=None)).status_code == 200
    assert orders_db[0]["ref_code"] == "Ab3_x-9" and orders_db[0]["ref_source"] is None


@pytest.mark.parametrize("change", [
    {"ref_slug": "other-store"},                    # a post of another store
    {"ref_at": now_ms() - 8 * DAY_MS},              # older than 7 days
    {"ref_at": now_ms() + 10 * 60 * 1000},          # 10 minutes in the future
    {"ref_at": None}, {"ref_slug": None}, {"ref_code": None},
])
def test_tc2_ref_not_kept(client, change):
    assert place(client, **good_ref(**change)).status_code == 200
    assert "ref_code" not in orders_db[0] and "ref_source" not in orders_db[0]


def test_tc2_no_ref_inserts_as_before(client):
    assert place(client).status_code == 200
    assert not any(k.startswith("ref") for k in orders_db[0])   # KT #2: the insert dict is unchanged


@pytest.mark.parametrize("change", [
    {"ref_code": "a b"}, {"ref_code": "x" * 70}, {"ref_code": 123}, {"ref_at": "abc"}, {"ref_at": True},
    {"ref_slug": ["nora"]}, {"ref_slug": "n" * 300},
])
def test_tc16_bad_ref_never_breaks_the_order(client, change):
    res = place(client, **good_ref(**change))
    assert res.status_code == 200, res.text
    assert "ref_code" not in orders_db[0]


def test_tc16_bad_source_keeps_ref_without_source(client):
    for source in ("Facebook", "", "x" * 40):
        orders_db.clear()
        assert place(client, **good_ref(ref_source=source)).status_code == 200
        assert orders_db[0]["ref_code"] == "Ab3_x-9" and orders_db[0]["ref_source"] is None


def test_tc17_double_submit_one_order_with_ref(client):
    assert place(client, **good_ref()).status_code == 200
    assert place(client, **good_ref()).status_code == 409
    assert len(orders_db) == 1 and orders_db[0]["ref_code"] == "Ab3_x-9"


def test_kt2_dao_inserts_ref_columns_only_with_a_ref():
    """KT #2 (QA #13): an order without a ref sends PostgREST exactly the old insert (no ref_* keys), so a schema
    cache that has not seen the new columns yet cannot break every order; one with a ref sends both."""
    import dao.dao_orders as dao_orders

    inserted = []

    class Table:
        def insert(self, data):
            inserted.append(data)
            return self

        def execute(self):
            return type("R", (), {"data": [inserted[-1]]})()

    dao = dao_orders.DAOOrders.__new__(dao_orders.DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, t: Table()})()
    money = {k: Decimal(0) for k in ("subtotal", "total_amount", "commission_rate", "commission_amount", "vat_rate",
                                     "vat_amount", "payout_amount")}
    dao.create_order(user_id="u", seller_id="s", seller_user_id="su", delivery_method="pickup", **money)
    dao.create_order(user_id="u", seller_id="s", seller_user_id="su", delivery_method="pickup", **money,
                     ref_code="p1", ref_source=None)
    assert not any(k.startswith("ref_") for k in inserted[0])
    assert inserted[1]["ref_code"] == "p1" and "ref_source" in inserted[1] and inserted[1]["ref_source"] is None


# ── ref-stats ────────────────────────────────────────────────────────────────

KEY = "studio-test-key"


class FakeRefOrders:
    since = None

    def read_ref_orders(self, seller_id, created_since):
        FakeRefOrders.since = created_since
        assert seller_id == "sid-nora"
        # what the DB filter returns: paid, not cancelled, this store, within the window
        return [{"ref_code": "p1", "ref_source": "fb", "subtotal": "120000.00"},
                {"ref_code": "p1", "ref_source": "fb", "subtotal": 85500},
                {"ref_code": "p2", "ref_source": None, "subtotal": "40000"}]


class FakeStores:
    def read_seller_by_slug_name(self, slug):
        return {"id": "sid-nora", "slug": "nora"} if slug == "nora" else None


@pytest.fixture
def stats(api, monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", KEY)
    monkeypatch.setattr(studio, "DAOOrders", FakeRefOrders)
    monkeypatch.setattr(studio, "DAOSellerProfiles", FakeStores)
    client = api(studio.router, user=None)
    return lambda key=KEY, **params: client.get("/studio/ref-stats", params={"slug": "nora", **params},
                                                headers={"X-Studio-Key": key} if key is not None else {})


def test_tc4_key(stats, monkeypatch):
    assert stats(key=None).status_code == 401
    assert stats(key="wrong").status_code == 401
    monkeypatch.setenv("STUDIO_API_KEY", "")
    assert stats().status_code == 503


def test_tc5_counts_and_totals(stats):
    res = stats()
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "nora" and body["days"] == 30
    assert sorted(body["refs"], key=lambda r: r["ref"]) == [
        {"ref": "p1", "source": "fb", "orders": 2, "items_total": 205500},
        {"ref": "p2", "source": None, "orders": 1, "items_total": 40000}]
    assert set(body) == {"success", "slug", "days", "refs"}   # no buyer data


def test_tc18_window_and_days(stats):
    assert stats(days=7).status_code == 200
    assert abs(datetime.now(timezone.utc) - timedelta(days=7) - FakeRefOrders.since) < timedelta(seconds=5)
    for bad in (0, 91, "abc"):
        assert stats(days=bad).status_code == 422
    assert stats(slug="nobody").status_code == 404


def test_tc18_query_counts_only_paid_not_cancelled(monkeypatch):
    """The DAO's filter itself (TC-18: a cancelled + refunded order stays 'paid', another store, older than the window)."""
    import dao.dao_orders as dao_orders

    calls = []

    class Query:
        def __getattr__(self, name):
            return lambda *a: calls.append((name, a)) or self

        @property
        def not_(self):
            calls.append(("not", ()))
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    dao = dao_orders.DAOOrders.__new__(dao_orders.DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, t: Query()})()
    since = datetime(2026, 11, 1, tzinfo=timezone.utc)
    dao.read_ref_orders("sid", since)
    assert ("eq", ("seller_id", "sid")) in calls
    assert ("not", ()) in calls and ("is_", ("ref_code", "null")) in calls
    assert ("eq", ("payment_status", "paid")) in calls
    assert ("neq", ("status", "cancelled")) in calls
    assert ("gte", ("created_at", since.isoformat())) in calls
