"""Background job health (docs/dev/20261106-job-health TC-1, 2, 9..13, 15..17). No DB: DAOs and Zalo are faked."""
import asyncio

import pytest

from services import api_metrics, job_health, order_expiry, payment_reconcile


class FakeDB:
    """metrics_job_health rows + the job_alert_failures setting; down=True makes every call fail."""
    def __init__(self):
        self.rows, self.writes, self.threshold, self.down = {}, [], 3, False

    def dao(self):
        db = self

        class DAO:
            def read_failures(self, job):
                if db.down:
                    raise Exception("db down")
                return db.rows.get(job, {}).get("failures", 0)

            def upsert(self, row):
                if db.down:
                    raise Exception("db down")
                db.writes.append(row)
                db.rows[row["job"]] = db.rows.get(row["job"], {}) | row
        return DAO()

    def config(self):
        db = self

        class Config:
            def get_positive_int(self, key, default):
                assert key == "job_alert_failures"
                if db.down:
                    raise Exception("db down")
                return db.threshold
        return Config()


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(job_health, "_failures", {})
    monkeypatch.setattr(job_health, "_alerted", set())
    monkeypatch.setattr(job_health, "_threshold", job_health.DEFAULT_ALERT_FAILURES)
    fake = FakeDB()
    monkeypatch.setattr(job_health, "DAOJobHealth", fake.dao)
    monkeypatch.setattr(job_health, "DAOAdminConfig", fake.config)
    fake.sent = []
    monkeypatch.setattr(job_health.zalo, "send", lambda kind, text: fake.sent.append((kind, text)))
    return fake


def fail(job="order_expiry", e=None):
    job_health.record(job, 60, e or Exception("boom"))


def ok(job="order_expiry"):
    job_health.record(job, 60)


def test_tc1_alert_once_at_threshold_then_recovery(db):  # TC-1
    ok()
    assert db.rows["order_expiry"]["failures"] == 0 and db.rows["order_expiry"]["last_ok_at"]
    fail(); fail()
    assert db.sent == [] and db.rows["order_expiry"]["failures"] == 2
    fail()
    assert len(db.sent) == 1 and db.sent[0][0] == "ops" and "3 failed runs in a row" in db.sent[0][1]
    fail()                                                     # 4th: no second message
    assert len(db.sent) == 1
    ok()
    assert len(db.sent) == 2 and "running again" in db.sent[1][1]
    row = db.rows["order_expiry"]
    assert row["failures"] == 0 and row["last_error"] == "Exception('boom')" and row["last_error_at"]
    ok()
    assert len(db.sent) == 2


def test_tc2_dao_error_never_raises(db, caplog):  # TC-2
    db.down = True
    ok(); fail()
    assert "not written" in caplog.text


def test_tc9_success_never_sends_error_keys(db):  # TC-9
    ok()
    fail(); ok()
    for row in (db.writes[0], db.writes[2]):
        assert set(row) == {"job", "interval_seconds", "last_run_at", "last_ok_at", "failures"} and row["failures"] == 0
    assert set(db.writes[1]) == {"job", "interval_seconds", "last_run_at", "last_error", "last_error_at", "failures"}


def test_tc10_supabase_down_still_alerts(db):  # TC-10
    db.down = True
    fail(); fail()
    assert db.sent == []
    fail()
    assert len(db.sent) == 1
    fail()
    assert len(db.sent) == 1


def test_tc10_last_threshold_read_is_kept(db):
    db.threshold = 5
    fail()                                                     # reads 5
    db.down = True
    fail(); fail()
    assert db.sent == []                                       # still 5, not the default 3
    fail(); fail()
    assert len(db.sent) == 1


def test_tc11_threshold_lowered_mid_streak(db):  # TC-11 case 1: >=, not ==
    db.threshold = 5
    for _ in range(4):
        fail()
    db.threshold = 3
    fail()
    assert len(db.sent) == 1


def test_tc11_threshold_lowered_after_alert(db):  # TC-11 case 2
    for _ in range(3):
        fail()
    db.threshold = 2
    fail()
    assert len(db.sent) == 1


def test_tc12_jobs_counted_apart(db):  # TC-12
    for _ in range(3):
        fail("order_expiry"); fail("payment_reconcile")
    assert len(db.sent) == 2
    ok("order_expiry")
    assert len(db.sent) == 3 and "Auto-cancel" in db.sent[2][1]
    assert db.rows["payment_reconcile"]["failures"] == 3
    fail("payment_reconcile")
    assert len(db.sent) == 3 and db.rows["payment_reconcile"]["failures"] == 4


def test_tc13_error_text_never_in_zalo(db):  # TC-13
    e = Exception("Failing row contains (0901234567, 12 Nguyen Hue, Quan 1) " + "x" * 600)
    for _ in range(3):
        fail(e=e)
    text = db.sent[0][1]
    assert "0901234567" not in text and "Nguyen Hue" not in text and "Failing" not in text
    assert "Auto-cancel of orders sellers did not accept" in text and "3 failed runs" in text and text.endswith("/monitoring")
    assert "0901234567" in db.rows["order_expiry"]["last_error"] and len(db.rows["order_expiry"]["last_error"]) == 500


def test_tc17_restart_after_alerted_streak(db):  # TC-17: the streak and its alert survive a restart
    db.rows["order_expiry"] = {"job": "order_expiry", "failures": 5}
    fail()                                                     # already alerted before the restart: no repeat
    assert db.sent == [] and db.rows["order_expiry"]["failures"] == 6
    ok()
    assert len(db.sent) == 1 and "running again" in db.sent[0][1]


def test_tc17_restart_below_threshold(db):
    db.rows["order_expiry"] = {"job": "order_expiry", "failures": 2}
    ok()
    assert db.sent == []


def test_tc16_helper_bug_never_reaches_loop(db, monkeypatch, caplog):  # TC-16, helper half
    monkeypatch.setattr(job_health, "_record", lambda *a: 1 / 0)
    ok()
    assert "not recorded" in caplog.text


# ─── loops (TC-15, TC-16) ──────────────────────────────────────────────────────
class Stop(Exception):
    pass


def run_loop(monkeypatch, loop, sleeps):
    """Run a loop until its `sleeps`-th asyncio.sleep; returns (to_thread calls, record calls)."""
    threaded, records, slept = [], [], []

    async def to_thread(fn, *args):
        threaded.append(fn)
        return fn(*args)

    async def sleep(seconds):
        slept.append(seconds)
        if len(slept) >= sleeps:
            raise Stop

    monkeypatch.setattr(asyncio, "to_thread", to_thread)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(job_health, "record", lambda job, interval, error=None: records.append((job, interval, error)))
    with pytest.raises(Stop):
        asyncio.run(loop())
    return threaded, records


def flaky(result=None):
    calls = []

    def fn(*a):
        calls.append(1)
        if len(calls) == 1:
            raise Exception("boom")
        return result
    return fn


def test_tc15_tc16_order_expiry_loop(monkeypatch):
    monkeypatch.setattr(order_expiry, "expire_unconfirmed_orders", flaky(0))
    threaded, records = run_loop(monkeypatch, order_expiry.run_order_expiry, 2)
    assert [(j, i, repr(e)) for j, i, e in records] == [("order_expiry", 60, "Exception('boom')"), ("order_expiry", 60, "None")]
    assert len(threaded) == 4 and threaded.count(job_health.record) == 2   # job + record each round, both threaded


def test_tc15_tc16_payment_reconcile_loop(monkeypatch):
    monkeypatch.setattr(payment_reconcile, "reconcile_payments", flaky({"tried": 0, "asked": 0, "errors": 0}))
    threaded, records = run_loop(monkeypatch, payment_reconcile.run_payment_reconcile, 2)
    assert [(j, i, e is None) for j, i, e in records] == [("payment_reconcile", 120, False), ("payment_reconcile", 120, True)]
    assert len(threaded) == 4


def test_reconcile_runs_without_an_ask_keep_the_last_result(monkeypatch):  # QĐ 3 (N3)
    runs = iter([{"tried": 2, "asked": 2, "errors": 2}, {"tried": 2, "asked": 0, "errors": 0},     # failed, kept
                 {"tried": 2, "asked": 2, "errors": 1}, {"tried": 1, "asked": 0, "errors": 0},     # one ask worked: ok
                 {"tried": 1, "asked": 1, "errors": 1}, {"tried": 0, "asked": 0, "errors": 0}])    # failed, then no order
    monkeypatch.setattr(payment_reconcile, "reconcile_payments", lambda: next(runs))
    _, records = run_loop(monkeypatch, payment_reconcile.run_payment_reconcile, 6)
    assert [e is not None for _, _, e in records] == [True, True, False, False, True, False]


def test_tc15_tc16_api_metrics_loop(monkeypatch):
    monkeypatch.setattr(api_metrics, "flush", flaky(0))
    monkeypatch.setattr(api_metrics, "cleanup", lambda: None)
    threaded, records = run_loop(monkeypatch, api_metrics.run_api_metrics, 3)   # sleeps before each run
    assert [(j, i, e is None) for j, i, e in records] == [("api_metrics", 300, False), ("api_metrics", 300, True)]
    assert len(threaded) == 5   # flush + record, then flush + cleanup + record
