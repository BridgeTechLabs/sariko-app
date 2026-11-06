"""Background jobs (docs/dev/20261106-job-health TC-1, 2, 9..13, 15..17; docs/dev/20261106-job-control TC-1..4, 12, 15,
18..20). No DB: DAOs, Zalo and the clock are faked."""
import asyncio
from datetime import datetime, timezone

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

            def update(self, job, values):
                if db.down:
                    raise Exception("db down")
                db.writes.append((job, values))
                db.rows[job] = db.rows.get(job, {}) | values

            def read_control(self, job, default_interval):
                if db.down:
                    raise Exception("db down")
                row = db.rows.setdefault(job, {})
                row.setdefault("paused", False)
                row.setdefault("interval_seconds", default_interval)
                return {"paused": row["paused"], "interval_seconds": row["interval_seconds"]}
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
    monkeypatch.setattr(job_health, "_control", {})
    monkeypatch.setattr(job_health, "_threshold", job_health.DEFAULT_ALERT_FAILURES)
    fake = FakeDB()
    monkeypatch.setattr(job_health, "DAOJobHealth", fake.dao)
    monkeypatch.setattr(job_health, "DAOAdminConfig", fake.config)
    fake.sent = []
    monkeypatch.setattr(job_health.zalo, "send", lambda kind, text: fake.sent.append((kind, text)))
    return fake


def fail(job="order_expiry", e=None):
    job_health.record(job, e or Exception("boom"))


def ok(job="order_expiry"):
    job_health.record(job)


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


def test_tc9_tc12_record_updates_only_its_columns(db):  # job-health TC-9, job-control TC-12
    ok()
    fail(); ok()
    for job, row in (db.writes[0], db.writes[2]):   # never interval_seconds / paused*: the admin sets those
        assert job == "order_expiry" and set(row) == {"last_run_at", "last_ok_at", "failures"} and row["failures"] == 0
    assert set(db.writes[1][1]) == {"last_run_at", "last_error", "last_error_at", "failures"}


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


# ─── every(): the 15-second tick (job-control TC-1..4, 15, 18..20; job-health TC-15, 16) ─────────────────────
class Stop(Exception):
    pass


def run_every(monkeypatch, db, ticks, run, interval=60, reset=None, before_tick=None):
    """every("order_expiry", interval, run) for `ticks` ticks on a fake clock (sleep moves it); before_tick(i) can
    change the row between ticks. Returns [(tick, "run" | "record:<error>" | "thread:<fn>")]."""
    clock, log = [0.0], []

    async def to_thread(fn, *args):
        log.append((len_ticks[0], f"thread:{fn.__name__}"))
        return fn(*args)

    async def sleep(seconds):
        assert seconds == job_health.TICK_SECONDS
        clock[0] += seconds
        len_ticks[0] += 1
        if len_ticks[0] >= ticks:
            raise Stop
        if before_tick:
            before_tick(len_ticks[0])

    len_ticks = [0]
    monkeypatch.setattr(job_health.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(asyncio, "to_thread", to_thread)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    real_record = job_health.record
    monkeypatch.setattr(job_health, "record", lambda job, error=None: (log.append((len_ticks[0], f"record:{error!r}")),
                                                                       real_record(job, error)))
    if before_tick:
        before_tick(0)

    def job():
        log.append((len_ticks[0], "run"))
        return run()
    with pytest.raises(Stop):
        asyncio.run(job_health.every("order_expiry", interval, job, reset))
    return log


def runs(log):
    return [t for t, what in log if what == "run"]


def test_runs_at_start_then_every_interval(monkeypatch, db):
    log = run_every(monkeypatch, db, 9, lambda: None)            # ticks every 15 s, interval 60 s
    assert runs(log) == [0, 4, 8]
    assert (0, "record:None") in log and (0, "thread:read_control") in log and (0, "thread:job") in log  # all threaded


def test_tc1_paused_neither_runs_nor_records(monkeypatch, db):  # TC-1, TC-19 (order_expiry paused)
    db.rows["order_expiry"] = {"paused": True}
    log = run_every(monkeypatch, db, 4, lambda: pytest.fail("ran while paused"))
    assert [w for _, w in log] == ["thread:read_control"] * 4     # read again every tick, nothing else


def test_tc19_paused_stays_paused_when_a_read_fails(monkeypatch, db):  # TC-19
    db.rows["order_expiry"] = {"paused": True}
    log = run_every(monkeypatch, db, 3, lambda: pytest.fail("ran while paused"),
                    before_tick=lambda i: setattr(db, "down", i == 1))
    assert runs(log) == []


def test_tc2_failed_read_keeps_the_last_interval(monkeypatch, db):  # TC-2
    db.rows["order_expiry"] = {"interval_seconds": 300}
    log = run_every(monkeypatch, db, 21, lambda: None, before_tick=lambda i: setattr(db, "down", i >= 1))
    assert runs(log) == [0, 20]                                    # 300 s kept, not the code default 60


def test_tc3_no_row_and_db_down_runs_with_the_code_default(monkeypatch, db):  # TC-3
    db.down = True
    log = run_every(monkeypatch, db, 5, lambda: None)
    assert runs(log) == [0, 4]


def test_tc15a_shorter_interval_applies_at_once(monkeypatch, db):  # TC-15 (a)
    db.rows["order_expiry"] = {"interval_seconds": 300}
    log = run_every(monkeypatch, db, 10, lambda: None,
                    before_tick=lambda i: i == 2 and db.rows["order_expiry"].update(interval_seconds=60))
    assert runs(log) == [0, 4, 8]                                  # 60 s after the last start, not 300


def test_tc15b_resume_runs_within_a_tick(monkeypatch, db):  # TC-15 (b)
    db.rows["order_expiry"] = {"interval_seconds": 300}
    log = run_every(monkeypatch, db, 6, lambda: None,
                    before_tick=lambda i: db.rows["order_expiry"].update(paused=i in (2, 3)))
    assert runs(log) == [0, 4]                                     # resumed at tick 4: runs at once


def test_tc16_failed_run_is_recorded_and_the_loop_goes_on(monkeypatch, db):  # job-health TC-16
    calls = []

    def run():
        calls.append(1)
        if len(calls) == 1:
            raise Exception("boom")
    log = run_every(monkeypatch, db, 5, run)
    assert [w for _, w in log if w.startswith("record")] == ["record:Exception('boom')", "record:None"]
    assert db.rows["order_expiry"]["last_error"] == "Exception('boom')"


def test_tc4_tc18_zalo_on_pause_and_resume_only(monkeypatch, db):  # TC-4, TC-18
    states = {0: True, 1: True, 2: False, 3: False, 4: True, 5: True, 6: False}
    run_every(monkeypatch, db, 7, lambda: None, before_tick=lambda i: db.rows.setdefault("order_expiry", {}).update(paused=states[i]))
    texts = [t for _, t in db.sent]
    assert len(texts) == 3                                         # none on the first read (paused at start)
    assert "resumed" in texts[0] and "paused" in texts[1] and "resumed" in texts[2]
    assert all("Auto-cancel of orders sellers did not accept" in t and t.endswith("/monitoring") for t in texts)
    assert not any("running again" in t or "@" in t for t in texts)


def test_tc18_first_read_fails_no_zalo(monkeypatch, db):  # TC-18: first read error, then paused
    run_every(monkeypatch, db, 3, lambda: None,
              before_tick=lambda i: (setattr(db, "down", i == 0), db.rows.setdefault("order_expiry", {}).update(paused=i >= 1)))
    assert db.sent == []                                           # the first good read only notes the state


def test_tc20_api_metrics_paused_keeps_nothing(monkeypatch, db):  # TC-20
    written, resumed_at = [], []
    monkeypatch.setattr(api_metrics, "DAOApiMetrics", lambda: type("D", (), {"insert_many": lambda self, rows: written.extend(rows)})())

    def before_tick(i):
        db.rows.setdefault("order_expiry", {}).update(paused=i < 3, interval_seconds=60)
        if i < 3:
            for _ in range(5):
                api_metrics.record("GET", "/rest/v1/cart", 200, 10)   # counted while paused: dropped
        if i == 3:
            resumed_at.append(datetime.now(timezone.utc).isoformat())
        if i == 4:
            api_metrics.record("GET", "/rest/v1/cart", 200, 10)
            api_metrics.record("GET", "/rest/v1/cart", 200, 10)
    log = run_every(monkeypatch, db, 8, api_metrics.flush, reset=api_metrics.take, before_tick=before_tick)
    assert runs(log) == [7]                                        # one full interval after the resume, not at once
    (row,) = written
    assert row["count"] == 2 and row["bucket_start"] >= resumed_at[0]


# ─── what each job runs ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("module, loop, job, interval, fn, reset", [
    (order_expiry, "run_order_expiry", "order_expiry", 60, "expire_unconfirmed_orders", None),
    (payment_reconcile, "run_payment_reconcile", "payment_reconcile", 120, "reconcile_run", None),
    (api_metrics, "run_api_metrics", "api_metrics", 300, "flush_and_cleanup", "take"),
])
def test_each_loop_is_every(monkeypatch, module, loop, job, interval, fn, reset):
    got = []

    async def every(*args, reset=None):
        got.append((*args, reset))
    monkeypatch.setattr(job_health, "every", every)
    asyncio.run(getattr(module, loop)())
    assert got == [(job, interval, getattr(module, fn), reset and getattr(module, reset))]


def test_reconcile_runs_without_an_ask_keep_the_last_result(monkeypatch):  # job-health QĐ 3 (N3)
    monkeypatch.setattr(payment_reconcile, "_vnpay_error", None)
    runs_ = iter([{"tried": 2, "asked": 2, "errors": 2}, {"tried": 2, "asked": 0, "errors": 0},     # failed, kept
                  {"tried": 2, "asked": 2, "errors": 1}, {"tried": 1, "asked": 0, "errors": 0},     # one ask worked: ok
                  {"tried": 1, "asked": 1, "errors": 1}, {"tried": 0, "asked": 0, "errors": 0}])    # failed, then no order
    monkeypatch.setattr(payment_reconcile, "reconcile_payments", lambda: next(runs_))
    failed = []
    for _ in range(6):
        try:
            payment_reconcile.reconcile_run()
            failed.append(False)
        except RuntimeError:
            failed.append(True)
    assert failed == [True, True, False, False, True, False]


def test_api_metrics_run_cleans_up_once_a_day(monkeypatch):
    calls = []
    monkeypatch.setattr(api_metrics, "_last_cleanup", None)
    monkeypatch.setattr(api_metrics, "flush", lambda: calls.append("flush"))
    monkeypatch.setattr(api_metrics, "cleanup", lambda: calls.append("cleanup"))
    api_metrics.flush_and_cleanup(); api_metrics.flush_and_cleanup()
    assert calls == ["flush", "cleanup", "flush"]
    monkeypatch.setattr(api_metrics, "flush", lambda: 1 / 0)          # a failed write fails the run, no cleanup
    with pytest.raises(ZeroDivisionError):
        api_metrics.flush_and_cleanup()
