"""T125: confirm VNPay payments whose IPN is late or lost (docs/dev/payment-confirm/README.md).

Every run: unpaid orders whose pay link is between payment_reconcile_after_minutes and
payment_reconcile_window_hours old are checked with VNPay (services/vnpay_query: at most once per 15 minutes
per link, never an order with a refund, never a link the IPN already answered).
  paid   -> apply_vnpay_result, the IPN's own handling (paid, withholding, seller push, payments row), + buyer push
  failed -> buyer push "not completed, you can pay again", once per link; payment_status stays 'pending'
  else   -> ask again later
Runs as a background loop in this process (lifespan.py), like order_expiry."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from apis.payments import apply_vnpay_result, querydr_params
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_orders import DAOOrders
from services import push_service, vnpay_query

logger = logging.getLogger(__name__)


def reconcile_payments(now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    config = DAOAdminConfig()
    after = timedelta(minutes=config.get_positive_int("payment_reconcile_after_minutes", 5))
    window = timedelta(hours=config.get_positive_int("payment_reconcile_window_hours", 24))
    dao = DAOOrders()
    counts = {"paid": 0, "failed": 0, "checked": 0}
    for order in dao.read_unpaid_vnpay_orders(created_since=now - window - timedelta(days=1)):
        txn = vnpay_query.current_txn(order)
        if not txn or not (after <= now - txn[1] <= window):
            continue
        try:
            outcome, check = vnpay_query.check_order(order, dao, now)
        except Exception as e:   # network / VNPay error: try again on a later run
            logger.warning(f"[Reconcile] order={order['id']} txn={txn[0]} check failed: {repr(e)}")
            continue
        counts["checked"] += outcome != "none"
        if outcome == "paid":
            rsp = json.loads(apply_vnpay_result(querydr_params(check)).body)
            logger.warning(f"[Reconcile] order={order['id']} txn={txn[0]} paid at VNPay, no IPN: {rsp}")
            if rsp["RspCode"] == "00":
                push_service.notify_payment_confirmed(order)
                counts["paid"] += 1
        elif outcome == "failed" and not order.get("vnpay_fail_notified_at"):
            dao.set_vnpay_fail_notified(order["id"], now)
            push_service.notify_payment_failed(order)
            counts["failed"] += 1
    return counts


async def run_payment_reconcile(interval_seconds: int = 120):
    while True:
        try:
            # The Supabase client and requests are synchronous: keep them off the event loop.
            await asyncio.to_thread(reconcile_payments)
        except Exception:
            logger.exception("[Reconcile] run failed")
        await asyncio.sleep(interval_seconds)
