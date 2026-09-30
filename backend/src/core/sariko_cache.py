"""Process-local TTL cache.

A small key/value store for answers that are expensive to compute and change
rarely — the kind of read that a polling client asks for over and over while
the underlying rows sit still.

Nothing expires in the background: an entry is dropped when it is read after
its deadline, so the store stays bounded by the number of distinct keys in use
rather than by traffic. Callers pick their own key format; a `<scope>_<id>_<what>`
convention keeps keys readable in logs and greppable back to the code that owns
them.

Safe under the threadpool FastAPI runs sync routes on — every operation takes
the lock.

WARNING — process-local, single worker only.
The Dockerfile runs `gunicorn -k uvicorn.workers.UvicornWorker` with no -w flag,
i.e. one worker, which is what makes this usable as a source of truth between
writes. Add workers and each process keeps its own copy: an invalidation served
by worker A leaves worker B's entry intact, worker B keeps serving the stale
value, and whoever polls worker B stops seeing updates until the TTL runs out.
Move to Redis before scaling out.
"""

import threading
import time
from typing import Any, Optional

DEFAULT_TTL_SECONDS = 30


class TTLCache:
    """Key/value store where every entry carries its own expiry deadline."""

    def __init__(self, default_ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self._default_ttl = default_ttl_seconds
        self._lock = threading.Lock()
        # key -> (expires_at_monotonic, value)
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Value for the key, or `default` when absent or expired.

        A miss and a cached None are indistinguishable through the default.
        Pass a sentinel as `default` if a caller ever needs to tell them apart.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return default

            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                return default

            return value

    def put(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Store the value, expiring after `ttl_seconds` (default TTL if None)."""
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._entries[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str) -> None:
        """Drop the key so the next read recomputes. No-op when absent."""
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        """Drop everything."""
        with self._lock:
            self._entries.clear()


# Shared instance. Use this unless a caller genuinely needs its own TTL or its
# own lifecycle — separate instances do not see each other's invalidations.
cache = TTLCache()
