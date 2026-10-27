"""T135 (docs/dev/monitoring Q1): how long each API takes. A middleware times every request (except /health) and
counts it in memory per (method, route pattern, status class); every FLUSH_SECONDS a background loop writes one row
per group to metrics_api (count, p50 / p95 / max in whole ms) and starts counting again. A failed write is
logged and that batch dropped: requests never wait on it. No IP, user or query string is kept. Once a day rows older
than api_metrics_retention_days are deleted."""
import asyncio
import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone

from dao.dao_admin_config import DAOAdminConfig
from dao.dao_api_metrics import DAOApiMetrics

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 300   # bucket length: a code constant, not a business parameter
SKIP_PATHS = {"/health"}

_lock = threading.Lock()
_samples = {}                                  # (method, route, status_class) -> [ms, ...]
_since = datetime.now(timezone.utc)            # start of the bucket being counted


def record(method: str, route: str, status: int, ms: int) -> None:
    with _lock:
        _samples.setdefault((method, route, f"{status // 100}xx"), []).append(ms)


async def middleware(request, call_next):
    """Registered in main.py inside CORS, outside the catch-all, so a 500 it makes is counted too."""
    if request.url.path in SKIP_PATHS:
        return await call_next(request)
    start = time.perf_counter()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path_format", None) or "(unmatched)"   # never the raw path
    record(request.method, route, response.status_code, round((time.perf_counter() - start) * 1000))
    return response


def _percentile(sorted_ms: list, p: float) -> int:
    """Nearest-rank percentile of an already sorted list."""
    return sorted_ms[max(math.ceil(p * len(sorted_ms)) - 1, 0)]


def take(now: datetime = None):
    """The bucket counted so far as rows, and a fresh bucket from now."""
    global _samples, _since
    now = now or datetime.now(timezone.utc)
    with _lock:
        samples, since = _samples, _since
        _samples, _since = {}, now
    rows = []
    for (method, route, status_class), ms in samples.items():
        ms.sort()
        rows.append({"bucket_start": since.isoformat(), "method": method, "route": route, "status_class": status_class,
                     "count": len(ms), "p50_ms": _percentile(ms, 0.5), "p95_ms": _percentile(ms, 0.95), "max_ms": ms[-1]})
    return rows


def flush(now: datetime = None) -> int:
    """Write the bucket; on a DB error log it and drop the batch (counting has already started again)."""
    rows = take(now)
    if not rows:
        return 0
    try:
        DAOApiMetrics().insert_many(rows)
        return len(rows)
    except Exception as e:
        logger.error(f"[ApiMetrics] {len(rows)} rows not written, dropped: {e!r}")
        return 0


def cleanup(now: datetime = None) -> str:
    """Delete rows older than api_metrics_retention_days; returns the cut-off used."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=DAOAdminConfig().get_positive_int("api_metrics_retention_days", 30))).isoformat()
    DAOApiMetrics().delete_before(cutoff)
    return cutoff


async def run_api_metrics():
    last_cleanup = None
    while True:
        await asyncio.sleep(FLUSH_SECONDS)
        try:
            await asyncio.to_thread(flush)
            today = datetime.now(timezone.utc).date()
            if last_cleanup != today:
                await asyncio.to_thread(cleanup)
                last_cleanup = today
        except Exception:
            logger.exception("[ApiMetrics] run failed")
