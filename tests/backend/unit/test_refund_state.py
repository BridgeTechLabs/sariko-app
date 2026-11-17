"""T172 (docs/dev/20261110-refund-state): order reads carry refund_state, the DB function's answer, instead of
the raw refunds rows. No DB, no network: the query builder is faked and records what is selected / filtered."""
import pytest

from dao.dao_orders import DAOOrders


class Query:
    """Stands for the PostgREST query builder: records select / filter calls, returns one row."""
    def __init__(self, calls):
        self.calls = calls

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args))
            return self
        return call

    def execute(self):
        row = {"id": "o1", "refund_state": None}
        return type("R", (), {"data": row if ("maybe_single", ()) in self.calls else [row]})()


@pytest.fixture
def selected(monkeypatch):
    calls = []
    dao = DAOOrders.__new__(DAOOrders)
    dao._table_name = "orders"
    dao._supabase_client = type("C", (), {"table": lambda self, name: Query(calls)})()
    return dao, calls


READS = {
    "buyer list": lambda dao: dao.read_orders_by_user_id("u1"),
    "buyer detail": lambda dao: dao.read_order_by_id("o1", "u1"),
    "seller detail": lambda dao: dao.read_order_by_id_for_seller("o1", "s1"),
}


@pytest.mark.parametrize("read", READS)
def test_order_reads_select_refund_state(selected, read):  # TC-3
    dao, calls = selected
    READS[read](dao)
    columns = [args[0] for name, args in calls if name == "select"][0]
    assert "refund_state" in [c.strip() for c in columns.split(",")]
    # the raw rows (and their duplicate_payment filter) are gone: the function decides
    assert "refunds(" not in columns
    assert not [args for name, args in calls if args and "refunds." in str(args[0])]
