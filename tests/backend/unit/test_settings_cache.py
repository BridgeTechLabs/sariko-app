"""admin_settings read through a 60 s cache (docs/dev/20261112-log-tick TC-9..12). The Supabase client is faked."""
import pytest

from core import sariko_cache
from dao.dao_admin_config import DAOAdminConfig


class FakeClient:
    def __init__(self, rows):
        self.rows, self.queries, self.down, self._keys, self._one = rows, [], False, None, False

    def table(self, name):
        assert name == "admin_settings"
        return self

    def select(self, _):
        return self

    def eq(self, _, key):
        self._keys, self._one = [key], True
        return self

    def in_(self, _, keys):
        self._keys, self._one = list(keys), False
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self.down:
            raise Exception("db down")
        self.queries.append(self._keys)
        data = [{"key": k, "value": self.rows[k]} for k in self._keys if k in self.rows]
        return type("R", (), {"data": (data[0] if data else None) if self._one else data})()


@pytest.fixture
def dao(monkeypatch):
    client = FakeClient({"a": 5, "b": 7})
    d = DAOAdminConfig.__new__(DAOAdminConfig)
    d._supabase_client = client
    return d


def ints(d, *keys):
    return d.get_positive_ints({k: 1 for k in keys})


def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(sariko_cache.time, "monotonic", lambda: now[0])
    return now


def test_tc9_second_read_inside_60s_is_cached(dao, monkeypatch):  # TC-9
    now = clock(monkeypatch)
    assert dao.get_setting("a") == 5 and dao.get_setting("a") == 5
    assert len(dao._supabase_client.queries) == 1
    now[0] += 61
    assert dao.get_setting("a") == 5
    assert len(dao._supabase_client.queries) == 2


def test_tc10_missing_key_none_is_cached(dao):  # TC-10
    assert dao.get_setting("zzz") is None and dao.get_setting("zzz") is None
    assert len(dao._supabase_client.queries) == 1


def test_tc11_positive_ints_asks_only_for_uncached_keys(dao):  # TC-11
    dao.get_setting("a")
    assert ints(dao, "a", "b") == {"a": 5, "b": 7}
    assert dao._supabase_client.queries == [["a"], ["b"]]
    assert ints(dao, "a", "b") == {"a": 5, "b": 7} and len(dao._supabase_client.queries) == 2   # nothing asked
    assert dao.get_setting("b") == 7 and len(dao._supabase_client.queries) == 2                 # shared cache keys
    assert dao.get_positive_int("a", 9) == 5


def test_tc11_missing_key_in_positive_ints_is_cached_as_default(dao):
    assert ints(dao, "zzz") == {"zzz": 1}
    assert ints(dao, "zzz") == {"zzz": 1} and len(dao._supabase_client.queries) == 1


def test_tc6_order_expiry_reads_its_two_keys_in_one_query(dao, monkeypatch):  # T200 TC-6
    from services import order_expiry
    monkeypatch.setattr(order_expiry, "DAOAdminConfig", lambda: dao)
    monkeypatch.setattr(order_expiry, "DAOOrders", lambda: type("O", (), {"read_unconfirmed_paid_orders": lambda s, paid_before: []})())
    order_expiry.expire_unconfirmed_orders()
    assert dao._supabase_client.queries == [["order_confirm_minutes", "order_confirm_reminder_minutes"]]


def test_tc6_payment_reconcile_reads_its_three_keys_in_one_query(dao, monkeypatch):  # T200 TC-6
    from services import payment_reconcile
    monkeypatch.setattr(payment_reconcile, "DAOAdminConfig", lambda: dao)
    monkeypatch.setattr(payment_reconcile, "DAOOrders", lambda: type("O", (), {
        "read_unpaid_vnpay_orders": lambda s, created_since: [], "read_expirable_unpaid_orders": lambda s, created_before: []})())
    payment_reconcile.reconcile_payments()
    payment_reconcile.expire_unpaid_orders()
    assert dao._supabase_client.queries == [["payment_reconcile_after_minutes", "payment_reconcile_window_hours", "unpaid_order_expire_minutes"]]


def test_tc12_db_error_raises_and_is_not_cached(dao):  # TC-12
    dao._supabase_client.down = True
    with pytest.raises(Exception):
        dao.get_setting("a")
    with pytest.raises(Exception):
        ints(dao, "b")
    dao._supabase_client.down = False
    assert dao.get_setting("a") == 5 and ints(dao, "b") == {"b": 7}
