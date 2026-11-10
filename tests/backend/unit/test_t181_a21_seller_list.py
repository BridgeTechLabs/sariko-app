"""sariko-app T181 A21 (docs/dev/20261110-audit-rest): a store's "my complaints" also lists the complaints others filed on
its orders, newest first, without listing its own twice. No DB: a fake client that answers the two queries."""
from dao.dao_complaints import DAOComplaints


class Query:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def __getattr__(self, name):
        def call(*a):
            self.log.append((name, a))
            return self
        return call

    def execute(self):
        return type("R", (), {"data": next(self.rows)})()


def test_a21b_own_and_about_my_orders_merged_newest_first():
    log = []
    answers = iter([[{"id": "own", "created_at": "2026-11-01"}], [{"id": "store-1"}], [{"id": "buyer", "created_at": "2026-11-05"}]])
    dao = DAOComplaints.__new__(DAOComplaints)
    dao._supabase_client = type("C", (), {"table": lambda self, n: Query(answers, log)})()
    assert [r["id"] for r in dao.list_by_user("u1")] == ["buyer", "own"]
    assert ("in_", ("orders.seller_id", ["store-1"])) in log and ("neq", ("user_id", "u1")) in log   # only its own stores' orders


def test_a21b_a_user_without_a_store_gets_only_their_own():
    log = []
    answers = iter([[{"id": "own", "created_at": "2026-11-01"}], []])
    dao = DAOComplaints.__new__(DAOComplaints)
    dao._supabase_client = type("C", (), {"table": lambda self, n: Query(answers, log)})()
    assert [r["id"] for r in dao.list_by_user("u1")] == ["own"]
    assert not any(name == "in_" for name, _ in log)   # no store: the join is never asked (an empty in_ would match nothing anyway)
