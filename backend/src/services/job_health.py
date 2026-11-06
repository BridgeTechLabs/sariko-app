"""Background jobs: run, health and control (docs/dev/20261106-job-health, 20261106-job-control).

every(job, default_interval, run) is the loop of each background job. Every TICK_SECONDS it reads the job's row in
metrics_job_health: paused -> skip; else, once interval_seconds have passed since the last run started, run() in a
thread and record() the result. A pause, resume or new interval set on the admin Monitoring page so applies within
one tick; a run in progress finishes. A failed read keeps the last values read (the code default before any), so a
config read never stops the job. A pause / resume seen by the loop sends one Zalo message (not on the process's
first read, so a deploy does not repeat "paused").

record(job, error) updates the job's last_* / failures columns (never interval_seconds or paused*, which the admin
sets). Failed runs in a row are counted in memory, seeded from the DB on the job's first run in this process so a
streak survives a restart. At job_alert_failures failures in a row the ops Zalo group gets one message, and one more
when the job runs again. Zalo is decided before the DB write and each DB step has its own try, so a Supabase outage
still sends the alert. record() never raises."""
import asyncio
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone

from dao.dao_admin_config import DAOAdminConfig
from dao.dao_job_health import DAOJobHealth
from services import zalo

logger = logging.getLogger(__name__)

# Plain words for the Zalo message (English, like the other Zalo messages). The error text is never sent:
# it can hold a receiver's phone or address.
NAMES = {
    "order_expiry": "Auto-cancel of orders sellers did not accept",
    "payment_reconcile": "VNPay payment check",
    "api_metrics": "API response-time recording",
}
DEFAULT_ALERT_FAILURES = 3
TICK_SECONDS = 15   # how soon a pause / resume / new interval applies; not a business parameter

_failures = {}                         # job -> failed runs in a row
_alerted = set()                       # jobs whose current failing streak already got a message
_threshold = DEFAULT_ALERT_FAILURES    # the last job_alert_failures read successfully
_control = {}                          # job -> (paused, interval_seconds) last read


def _send(text: str) -> None:
    zalo.send("ops", f"{text}\n{zalo.link('/monitoring')}")


def read_control(job: str, default_interval: int) -> tuple:
    """(paused, interval_seconds) of the job; never raises."""
    try:
        row = DAOJobHealth().read_control(job, default_interval)
        new = (bool(row["paused"]), int(row["interval_seconds"]))
    except Exception as e:
        logger.error(f"[JobHealth] {job} control not read, keeping the last values: {e!r}")
        return _control.get(job, (False, default_interval))
    old = _control.get(job)
    _control[job] = new
    if old is not None and old[0] != new[0]:
        name = NAMES.get(job, job)
        _send(f"⏸️ Background job paused: {name} · it will not run until someone resumes it on the Monitoring page"
              if new[0] else f"▶️ Background job resumed: {name}")
    return new


async def every(job: str, default_interval: int, run, reset=None) -> None:
    """The loop of a background job. reset (api_metrics: drop what was counted) is called on every paused tick and
    before the first wait, for a job whose run covers the time since the previous one: it then runs one full interval
    after start / resume instead of at once."""
    started = None   # time.monotonic() when the last run started; None = run at once (start, or just resumed)
    while True:
        paused, interval = await asyncio.to_thread(read_control, job, default_interval)
        if paused:
            started = None
            if reset:
                reset()
        elif started is None and reset:
            reset()
            started = time.monotonic()
        elif started is None or time.monotonic() - started >= interval:
            started = time.monotonic()
            error = None
            try:
                await asyncio.to_thread(run)   # the Supabase client is synchronous: keep it off the event loop
            except Exception as e:
                logger.exception(f"[{job}] run failed")
                error = e
            await asyncio.to_thread(record, job, error)
        await asyncio.sleep(TICK_SECONDS)


def _read_threshold() -> None:
    global _threshold
    try:
        _threshold = DAOAdminConfig().get_positive_int("job_alert_failures", DEFAULT_ALERT_FAILURES)
    except Exception as e:
        logger.error(f"[JobHealth] job_alert_failures not read, using {_threshold}: {e!r}")


def record(job: str, error: Exception = None) -> None:
    try:
        _record(job, error)
    except Exception:
        logger.exception(f"[JobHealth] {job} not recorded")


def _record(job: str, error: Exception) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if job not in _failures:   # first run in this process: carry on a streak (and its alert) from before a restart
        try:
            _failures[job] = DAOJobHealth().read_failures(job)
        except Exception as e:
            logger.error(f"[JobHealth] {job} failures not read, starting from 0: {e!r}")
            _failures[job] = 0
        if _failures[job]:
            _read_threshold()
            if _failures[job] >= _threshold:
                _alerted.add(job)
    failures = 0 if error is None else _failures[job] + 1
    _failures[job] = failures

    if error is not None:
        _read_threshold()
        if failures >= _threshold and job not in _alerted:
            _alerted.add(job)
            _send(f"⚠️ Background job failing: {NAMES.get(job, job)} · {failures} failed runs in a row")
    elif job in _alerted:
        _alerted.discard(job)
        _send(f"✅ Background job running again: {NAMES.get(job, job)}")

    values = {"last_run_at": now, "failures": failures}
    # a success never sends last_error / last_error_at: the last error stays visible on the Monitoring page
    values |= {"last_ok_at": now} if error is None else {"last_error": repr(error)[:500], "last_error_at": now}
    try:
        DAOJobHealth().update(job, values)
    except Exception as e:
        logger.error(f"[JobHealth] {job} not written: {e!r}")
    _ping(job, error is not None)


def _ping(job: str, failed: bool) -> None:
    """Healthchecks.io (20261106-job-control QĐ 8): a check per job, <ENV>-job-<job>, made on the first ping; a failed
    run pings /fail, a paused job does not ping at all (it is not recorded), so Healthchecks reports a job that stopped
    or stayed paused too long, even when this process is dead. No HC_PING_KEY = nothing. Never raises."""
    key = os.getenv("HC_PING_KEY")
    if not key:
        return
    slug = f"{os.getenv('ENV', 'local')}-job-{job.replace('_', '-')}"
    try:
        urllib.request.urlopen(f"https://hc-ping.com/{key}/{slug}{'/fail' if failed else ''}?create=1", timeout=10).close()
    except Exception as e:   # the key is in the URL: log the error type only
        logger.warning(f"[JobHealth] {job} Healthchecks ping not sent: {type(e).__name__}")
