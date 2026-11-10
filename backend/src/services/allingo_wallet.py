"""T162: tell the admins the AllinGo wallet is running low before trips start failing (docs/dev/20261110-allingo-wallet).

A background loop (lifespan.py) runs only when both AllinGo keys are set, whatever the delivery switch says, so the
wallet is watched before AllinGo is turned on. It reads GET /wallet at the interval set on the Monitoring page (row
'allingo_wallet', 30 minutes from the migration). A balance below admin_settings allingo_wallet_alert_vnd alerts at
once (push + ops Zalo), then at most every allingo_wallet_alert_repeat_hours while it stays below; a balance at or
above it resets that. A failed wallet read raises, so job_health counts it, and changes nothing here."""
import logging
import os
import time

from dao.dao_admin_config import DAOAdminConfig
from services import allingo_service, job_health, push_service, zalo

logger = logging.getLogger(__name__)

DEFAULTS = {"allingo_wallet_alert_vnd": 500000, "allingo_wallet_alert_repeat_hours": 6}
_settings = dict(DEFAULTS)   # the last values read
# ponytail: kept in this process only (one worker), so a restart while the wallet is low alerts once more
_alerted_at = None           # time.monotonic() of the last alert while below the threshold, None = not below


def check() -> None:
    global _settings, _alerted_at
    balance = allingo_service.get_allingo_service().wallet_balance()
    try:
        _settings = DAOAdminConfig().get_positive_ints(DEFAULTS)
    except Exception as e:
        logger.error(f"[AllinGoWallet] settings not read, using {_settings}: {e!r}")
    threshold = _settings["allingo_wallet_alert_vnd"]
    if balance >= threshold:
        _alerted_at = None
    elif _alerted_at is None or time.monotonic() - _alerted_at >= _settings["allingo_wallet_alert_repeat_hours"] * 3600:
        _alerted_at = time.monotonic()
        push_service.notify_admins("admin_delivery_wallet_low", "/monitoring",
                                   balance=zalo.vnd(balance), threshold=zalo.vnd(threshold))


async def run_allingo_wallet():
    if os.getenv("ALLINGO_APP_ID") and os.getenv("ALLINGO_APP_SECRET"):   # what AllingoService() needs
        await job_health.every("allingo_wallet", 1800, check)
