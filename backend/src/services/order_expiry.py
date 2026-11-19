"""Auto-cancel + refund paid orders the seller didn't accept in time: same-day orders
(admin_settings.order_confirm_minutes, 30 by default) while the store was open, pre-orders
(preorder_confirm_minutes, 720 by default) from payment, open or closed.
order_confirm_reminder_minutes before that, the seller and every admin device get a push.

Runs as a background loop in this process (see lifespan.py). The cancel is
conditional on the order still being pending, so a seller who acts at the same
moment wins cleanly, and refunds_order_id_key stops a second refund.
"""
import logging
import math
from datetime import datetime, timedelta, timezone

from core.store_hours import confirm_deadline, is_open_now
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_orders import DAOOrders, preorder_days
from dao.dao_refunds import DAORefunds
from services import job_health, push_service

logger = logging.getLogger(__name__)

DEFAULT_CONFIRM_MINUTES = 30
DEFAULT_PREORDER_CONFIRM_MINUTES = 720
DEFAULT_REMINDER_MINUTES = 10
TIMEOUT_REASON = "seller_timeout"  # orders.cancellation_reason code, translated by each viewer's app (T178)


def _ts(value):
    return datetime.fromisoformat(value) if value else None


def confirm_window() -> timedelta:
    """Read on every run, so a change in admin_settings applies within a minute."""
    return DAOAdminConfig().get_minutes("order_confirm_minutes", DEFAULT_CONFIRM_MINUTES)


def preorder_window() -> timedelta:
    return DAOAdminConfig().get_minutes("preorder_confirm_minutes", DEFAULT_PREORDER_CONFIRM_MINUTES)


def order_deadline(order: dict, seller: dict, now: datetime, window: timedelta, preorder: timedelta):
    """When a paid order the seller hasn't accepted auto-cancels: the one rule for this job, the seller's
    countdown and the buyer's "confirm by". A pre-order (a dish cooked days ahead): `preorder` from payment,
    open or closed (the seller may only look in the evening), never past the delivery time.
    A same-day order: `window` (confirm_deadline); None while the store is closed, that clock is paused."""
    paid_at = _ts(order["paid_at"])
    if preorder_days(order):
        appointment = _ts(order.get("delivery_appointment"))
        return min(paid_at + preorder, appointment) if appointment else paid_at + preorder
    hours = seller.get("weekly_hours")
    if not is_open_now(seller.get("is_open"), hours, now, seller.get("id")):
        return None
    return confirm_deadline(paid_at, hours, _ts(seller.get("opened_at")), now, window, seller.get("id"))


# Orders the seller was already reminded about. In memory: a restart may remind once more.
_reminded: set = set()


def expire_unconfirmed_orders(now: datetime = None) -> int:
    now = now or datetime.now(timezone.utc)
    minutes = DAOAdminConfig().get_positive_ints({"order_confirm_minutes": DEFAULT_CONFIRM_MINUTES,
                                                  "preorder_confirm_minutes": DEFAULT_PREORDER_CONFIRM_MINUTES,
                                                  "order_confirm_reminder_minutes": DEFAULT_REMINDER_MINUTES})
    window = timedelta(minutes=minutes["order_confirm_minutes"])
    preorder = timedelta(minutes=minutes["preorder_confirm_minutes"])
    reminder = timedelta(minutes=minutes["order_confirm_reminder_minutes"])
    dao_orders = DAOOrders()
    expired = 0
    waiting = dao_orders.read_unconfirmed_paid_orders(paid_before=now - max(min(window, preorder) - reminder, timedelta(0)))
    _reminded.intersection_update(order["id"] for order in waiting)  # forget orders that moved on
    for order in waiting:
        deadline = order_deadline(order, order.get("seller_profiles") or {}, now, window, preorder)
        if deadline is None:
            continue
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


async def run_order_expiry():
    await job_health.every("order_expiry", 60, expire_unconfirmed_orders)
