"""Auto-cancel + refund paid orders the seller didn't accept in time
(admin_settings.order_confirm_minutes, 30 by default) while the store was open.
order_confirm_reminder_minutes before that, the seller and every admin device get a push.

Runs as a background loop in this process (see lifespan.py). The cancel is
conditional on the order still being pending, so a seller who acts at the same
moment wins cleanly, and refunds_order_id_key stops a second refund.
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

from core.store_hours import confirm_deadline, is_open_now
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_orders import DAOOrders
from dao.dao_refunds import DAORefunds
from services import push_service

logger = logging.getLogger(__name__)

DEFAULT_CONFIRM_MINUTES = 30
DEFAULT_REMINDER_MINUTES = 10
TIMEOUT_REASON = "Seller did not confirm in time"  # the buyer UI translates this exact text (OrderStatusHeader.vue)


def _ts(value):
    return datetime.fromisoformat(value) if value else None


def confirm_window() -> timedelta:
    """Read on every run, so a change in admin_settings applies within a minute."""
    return DAOAdminConfig().get_minutes("order_confirm_minutes", DEFAULT_CONFIRM_MINUTES)


# Orders the seller was already reminded about. In memory: a restart may remind once more.
_reminded: set = set()


def expire_unconfirmed_orders(now: datetime = None) -> int:
    now = now or datetime.now(timezone.utc)
    window = confirm_window()
    reminder = DAOAdminConfig().get_minutes("order_confirm_reminder_minutes", DEFAULT_REMINDER_MINUTES)
    dao_orders = DAOOrders()
    expired = 0
    waiting = dao_orders.read_unconfirmed_paid_orders(paid_before=now - max(window - reminder, timedelta(0)))
    _reminded.intersection_update(order["id"] for order in waiting)  # forget orders that moved on
    for order in waiting:
        seller = order.get("seller_profiles") or {}
        opening, closing = seller.get("opening_time"), seller.get("closing_time")
        if not is_open_now(seller.get("is_open"), opening, closing, now):
            continue
        deadline = confirm_deadline(_ts(order["paid_at"]), opening, closing, _ts(seller.get("opened_at")), now, window)
        if now < deadline:
            if now >= deadline - reminder and order["id"] not in _reminded:
                _reminded.add(order["id"])
                push_service.notify_seller_order_expiring(order)
                push_service.notify_admins("admin_order_expiring", f"/orders?open={order['id']}", code=order["id"][:8],
                                           minutes=math.ceil((deadline - now).total_seconds() / 60))
            continue
        cancelled = dao_orders.update_order_status(order["id"], "cancelled", TIMEOUT_REASON, expected_status="pending")
        if not cancelled:
            continue  # the seller acted first
        DAORefunds().create_refund_for_order(order, "seller_timeout")
        push_service.notify_seller_order_expired(cancelled)
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
