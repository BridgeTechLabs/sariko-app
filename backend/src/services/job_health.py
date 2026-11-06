"""Background job health (docs/dev/20261106-job-health). Every run of a background loop calls
record(job, interval_seconds, error) through asyncio.to_thread; it upserts the job's row in metrics_job_health
(read by the admin Monitoring page). Failed runs in a row are counted in memory, seeded from the DB on the job's
first run in this process so a streak survives a restart. At job_alert_failures failures in a row the ops Zalo
group gets one message, and one more when the job runs again. Zalo is decided before the DB write and each DB
step has its own try, so a Supabase outage still sends the alert. record() never raises."""
import logging
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

_failures = {}                         # job -> failed runs in a row
_alerted = set()                       # jobs whose current failing streak already got a message
_threshold = DEFAULT_ALERT_FAILURES    # the last job_alert_failures read successfully


def _read_threshold() -> None:
    global _threshold
    try:
        _threshold = DAOAdminConfig().get_positive_int("job_alert_failures", DEFAULT_ALERT_FAILURES)
    except Exception as e:
        logger.error(f"[JobHealth] job_alert_failures not read, using {_threshold}: {e!r}")


def record(job: str, interval_seconds: int, error: Exception = None) -> None:
    try:
        _record(job, interval_seconds, error)
    except Exception:
        logger.exception(f"[JobHealth] {job} not recorded")


def _record(job: str, interval_seconds: int, error: Exception) -> None:
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

    name, url = NAMES.get(job, job), zalo.link("/monitoring")
    if error is not None:
        _read_threshold()
        if failures >= _threshold and job not in _alerted:
            _alerted.add(job)
            zalo.send("ops", f"⚠️ Background job failing: {name} · {failures} failed runs in a row\n{url}")
    elif job in _alerted:
        _alerted.discard(job)
        zalo.send("ops", f"✅ Background job running again: {name}\n{url}")

    row = {"job": job, "interval_seconds": interval_seconds, "last_run_at": now, "failures": failures}
    # a success never sends last_error / last_error_at: the last error stays visible on the Monitoring page
    row |= {"last_ok_at": now} if error is None else {"last_error": repr(error)[:500], "last_error_at": now}
    try:
        DAOJobHealth().upsert(row)
    except Exception as e:
        logger.error(f"[JobHealth] {job} not written: {e!r}")
