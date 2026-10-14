"""Auto-cancel + refund paid orders the seller didn't accept in time
(admin_settings.order_confirm_minutes, 30 by default) while the store was open.

Runs as a background loop in this process (see lifespan.py). The cancel is
conditional on the order still being pending, so a seller who acts at the same
moment wins cleanly, and refunds_order_id_key stops a second refund.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from core.store_hours import confirm_deadline, is_open_now
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_orders import DAOOrders
from dao.dao_refunds import DAORefunds

logger = logging.getLogger(__name__)

DEFAULT_CONFIRM_MINUTES = 30
TIMEOUT_REASON = "Seller did not confirm in time"


def _ts(value):
    return datetime.fromisoformat(value) if value else None


def confirm_window() -> timedelta:
    """Read on every run, so a change in admin_settings applies within a minute.
    A missing or invalid value falls back to the default rather than letting a
    typo (0, "abc") cancel every waiting order at once."""
    value = DAOAdminConfig().get_setting("order_confirm_minutes")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return timedelta(minutes=value)
    logger.error(f"[Expiry] invalid order_confirm_minutes={value!r}, using {DEFAULT_CONFIRM_MINUTES}")
    return timedelta(minutes=DEFAULT_CONFIRM_MINUTES)


def expire_unconfirmed_orders(now: datetime = None) -> int:
    now = now or datetime.now(timezone.utc)
    window = confirm_window()
    dao_orders = DAOOrders()
    expired = 0
    for order in dao_orders.read_unconfirmed_paid_orders(paid_before=now - window):
        seller = order.get("seller_profiles") or {}
        opening, closing = seller.get("opening_time"), seller.get("closing_time")
        if not is_open_now(seller.get("is_open"), opening, closing, now):
            continue
        if now < confirm_deadline(_ts(order["paid_at"]), opening, closing, _ts(seller.get("opened_at")), now, window):
            continue
        if not dao_orders.update_order_status(order["id"], "cancelled", TIMEOUT_REASON, expected_status="pending"):
            continue  # the seller acted first
        DAORefunds().create_refund_for_order(order, "seller_timeout")
        logger.warning(f"[Expiry] order={order['id']} cancelled: seller did not confirm in time")
        expired += 1
    return expired


async def run_order_expiry(interval_seconds: int = 60):
    while True:
        try:
            # The Supabase client is synchronous: keep it off the event loop.
            await asyncio.to_thread(expire_unconfirmed_orders)
        except Exception:
            logger.exception("[Expiry] run failed")
        await asyncio.sleep(interval_seconds)
