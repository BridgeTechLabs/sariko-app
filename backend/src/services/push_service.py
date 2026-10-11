import json
import logging
import os
import threading

from pywebpush import webpush, WebPushException

from dao.dao_push_subscriptions import DAOPushSubscriptions
from dao.dao_users import DAOUsers

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", None)
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:support@sariko.store")

# Keep undelivered pushes for a day (device offline) — pywebpush defaults to 0 = drop.
PUSH_TTL_SECONDS = 24 * 60 * 60

# event → {lang: (title, body)}
MESSAGES = {
    "new_order": {
        "en": ("New order 🎉", "A customer just paid for an order. Tap to confirm it."),
        "vi": ("Có đơn hàng mới 🎉", "Khách vừa thanh toán một đơn hàng. Nhấn để xác nhận."),
    },
    "confirmed": {
        "en": ("Order confirmed", "The seller accepted your order and is preparing it."),
        "vi": ("Đơn hàng đã được xác nhận", "Người bán đã nhận đơn và đang chuẩn bị."),
    },
    "ready": {
        "en": ("Order ready", "Your order is ready — delivery is being arranged."),
        "vi": ("Đơn hàng đã sẵn sàng", "Món đã xong, đang sắp xếp giao hàng."),
    },
    "done": {
        "en": ("Order delivered", "Enjoy your meal! Tap to leave a review."),
        "vi": ("Đã giao hàng", "Chúc ngon miệng! Nhấn để đánh giá món."),
    },
    "cancelled": {
        "en": ("Order cancelled", "Your order was cancelled. Tap to see details."),
        "vi": ("Đơn hàng đã bị hủy", "Nhấn để xem chi tiết."),
    },
    "delivery_failed": {
        "en": ("Delivery problem", "Your delivery couldn't be completed. Tap to see details."),
        "vi": ("Giao hàng không thành công", "Không giao được đơn hàng. Nhấn để xem chi tiết."),
    },
    "seller_delivery_failed": {
        "en": ("Delivery failed", "A delivery couldn't be completed. Tap to rebook a driver."),
        "vi": ("Giao hàng thất bại", "Một đơn không giao được. Nhấn để đặt lại tài xế."),
    },
    "seller_buyer_cancelled": {
        "en": ("Order cancelled by customer", "A customer cancelled a paid order. Tap to see details."),
        "vi": ("Khách đã hủy đơn", "Khách vừa hủy một đơn đã thanh toán. Nhấn để xem chi tiết."),
    },
}


def notify_new_order(order: dict):
    """Seller side: the order just became paid, i.e. it just entered the seller's list."""
    _send_async(order.get("seller_user_id"), "new_order", f"/seller/orders/{order['id']}")


def notify_order_status(order: dict):
    """Called with the updated orders row after every status change."""
    # Unpaid orders never reached the seller — e.g. the cancel after a failed
    # create_order. Nothing worth telling anyone.
    if order.get("payment_status") != "paid":
        return

    status = order.get("status")
    if status in MESSAGES:
        _send_async(order.get("user_id"), status, f"/orders/{order['id']}")
    if status == "delivery_failed":
        _send_async(order.get("seller_user_id"), "seller_delivery_failed", f"/seller/orders/{order['id']}")


def notify_buyer_cancelled(order: dict):
    """Seller side: the buyer cancelled an order the seller had already seen (paid).
    Called from the buyer cancel API — the DAO hook can't tell who cancelled."""
    if order.get("payment_status") != "paid":
        return
    _send_async(order.get("seller_user_id"), "seller_buyer_cancelled", f"/seller/orders/{order['id']}")


def _send_async(user_id, event: str, url: str):
    # Push services can take seconds to answer; never hold up the request
    # (or the VNPay IPN) that changed the order.
    if not user_id or not VAPID_PRIVATE_KEY:
        return
    threading.Thread(target=_send, args=(user_id, event, url), daemon=True).start()


def _send(user_id: str, event: str, url: str):
    try:
        dao_subs = DAOPushSubscriptions()
        subscriptions = dao_subs.read_subscriptions_by_user_id(user_id)
        if not subscriptions:
            return

        user = DAOUsers().get_users(user_id=user_id)
        lang = "vi" if user and user.get("preferred_language") == "Tiếng Việt" else "en"
        title, body = MESSAGES[event][lang]
        payload = json.dumps({"title": title, "body": body, "url": url})

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": VAPID_SUBJECT},  # fresh dict: webpush writes aud/exp into it
                    ttl=PUSH_TTL_SECONDS,
                )
            except WebPushException as e:
                # 404/410 = the browser unsubscribed (sign-out, toggle off, cleared data)
                if e.response is not None and e.response.status_code in (404, 410):
                    dao_subs.delete_subscription(sub["endpoint"])
                else:
                    logger.warning(f"push_service - webpush failed for user {user_id}: {repr(e)}")

    except Exception as e:
        logger.exception(f"push_service - _send failed for user {user_id}, event {event}: {repr(e)}")
