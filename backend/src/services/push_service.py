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
    "seller_driver_assigned": {
        "en": ("Driver on the way", "A driver accepted the delivery and is coming to pick up the order."),
        "vi": ("Đã có tài xế", "Tài xế đã nhận đơn và đang đến lấy hàng."),
    },
    "seller_delivered": {
        "en": ("Order delivered", "The driver has delivered the order to the customer."),
        "vi": ("Đã giao hàng thành công", "Tài xế đã giao đơn hàng đến khách."),
    },
    "seller_buyer_cancelled": {
        "en": ("Order cancelled by customer", "A customer cancelled a paid order. Tap to see details."),
        "vi": ("Khách đã hủy đơn", "Khách vừa hủy một đơn đã thanh toán. Nhấn để xem chi tiết."),
    },
    "seller_order_expiring": {
        "en": ("Order about to auto-cancel", "A paid order hasn't been accepted yet. Accept it in the next few minutes or it will be cancelled and refunded."),
        "vi": ("Đơn sắp tự hủy", "Một đơn đã thanh toán chưa được nhận. Hãy nhận đơn trong vài phút tới, nếu không đơn sẽ tự hủy và hoàn tiền cho khách."),
    },
    "seller_complaint": {
        "en": ("New complaint on an order", "A customer filed a complaint about an order. Tap to see it."),
        "vi": ("Có khiếu nại về đơn hàng", "Khách vừa gửi khiếu nại về một đơn hàng. Nhấn để xem."),
    },
    "seller_order_expired": {
        "en": ("Order cancelled: not confirmed in time", "A paid order wasn't confirmed in time, so it was cancelled and the customer will be refunded."),
        "vi": ("Đơn đã tự hủy", "Một đơn đã thanh toán không được xác nhận kịp thời nên đã bị hủy, khách sẽ được hoàn tiền."),
    },
    # Admin panel (notify_admins): {fields} come from the caller, {category} is translated below.
    "admin_new_complaint": {
        "en": ("New complaint {code}", "{category}. Tap to open it."),
        "vi": ("Khiếu nại mới {code}", "{category}. Nhấn để xem."),
    },
    "admin_order_expiring": {
        "en": ("Order #{code} not accepted", "{minutes} min left before it auto-cancels. Call the seller."),
        "vi": ("Đơn #{code} chưa được nhận", "Còn {minutes} phút trước khi tự hủy. Hãy gọi người bán."),
    },
    "admin_delivery_failed": {
        "en": ("Order #{code}: delivery failed", "Lalamove could not deliver it. Tap to open the order."),
        "vi": ("Đơn #{code} giao thất bại", "Lalamove không giao được. Nhấn để mở đơn."),
    },
}

# Complaint types (apis/complaints.py CATEGORIES), same words as the app's complaint form.
COMPLAINT_CATEGORIES = {
    "wrong_item": {"en": "Not as described", "vi": "Không đúng mô tả"},
    "damaged": {"en": "Damaged or unsafe", "vi": "Hư hỏng hoặc không an toàn"},
    "missing_item": {"en": "Missing item", "vi": "Thiếu món"},
    "late": {"en": "Late or not delivered", "vi": "Giao trễ hoặc không giao"},
    "buyer_issue": {"en": "Problem with the customer", "vi": "Vấn đề với khách hàng"},
    "delivery_issue": {"en": "Delivery problem", "vi": "Vấn đề giao hàng"},
    "payment_issue": {"en": "Payment or payout", "vi": "Thanh toán hoặc chi trả"},
    "other": {"en": "Other", "vi": "Khác"},
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


def notify_seller_order_expiring(order: dict):
    """Seller side: a paid order is close to auto-cancelling (admin_settings.order_confirm_reminder_minutes)."""
    _send_async(order.get("seller_user_id"), "seller_order_expiring", f"/seller/orders/{order['id']}")


def notify_seller_order_expired(order: dict):
    """Seller side: the confirm-timeout job cancelled a paid order the seller never answered.
    notify_order_status already told the buyer."""
    _send_async(order.get("seller_user_id"), "seller_order_expired", f"/seller/orders/{order['id']}")


def notify_seller_driver_assigned(order: dict):
    """Seller side: Lalamove assigned a driver (again, if the first one cancelled). Called from the webhook."""
    _send_async(order.get("seller_user_id"), "seller_driver_assigned", f"/seller/orders/{order['id']}")


def notify_seller_delivered(order: dict):
    """Seller side: Lalamove reported the delivery COMPLETED.
    Called from the webhook — a seller marking 'done' themselves needs no push."""
    _send_async(order.get("seller_user_id"), "seller_delivered", f"/seller/orders/{order['id']}")


def notify_seller_complaint(seller_user_id, order_id: str):
    """Seller side: the buyer filed a complaint about this order (T35)."""
    _send_async(seller_user_id, "seller_complaint", f"/seller/orders/{order_id}")


def notify_admins(event: str, url: str, **fields):
    """Admin panel: every admin-app subscription gets it (no admin roles). url is an admin-panel path."""
    if not VAPID_PRIVATE_KEY:
        return
    threading.Thread(target=_send_admins, args=(event, url, fields), daemon=True).start()


def _send_admins(event: str, url: str, fields: dict):
    try:
        by_user = {}
        for sub in DAOPushSubscriptions().read_admin_subscriptions():
            by_user.setdefault(sub["user_id"], []).append(sub)
        for user_id, subscriptions in by_user.items():
            _deliver(user_id, subscriptions, event, url, fields)
    except Exception as e:
        logger.exception(f"push_service - _send_admins failed for event {event}: {repr(e)}")


def _send_async(user_id, event: str, url: str):
    # Push services can take seconds to answer; never hold up the request
    # (or the VNPay IPN) that changed the order.
    if not user_id or not VAPID_PRIVATE_KEY:
        return
    threading.Thread(target=_send, args=(user_id, event, url), daemon=True).start()


def _send(user_id: str, event: str, url: str):
    try:
        subscriptions = DAOPushSubscriptions().read_subscriptions_by_user_id(user_id)
        if subscriptions:
            _deliver(user_id, subscriptions, event, url, {})
    except Exception as e:
        logger.exception(f"push_service - _send failed for user {user_id}, event {event}: {repr(e)}")


def _message(event: str, lang: str, fields: dict):
    title, body = MESSAGES[event][lang]
    if "category" in fields:
        fields = {**fields, "category": COMPLAINT_CATEGORIES.get(fields["category"], {}).get(lang, fields["category"])}
    return title.format(**fields), body.format(**fields)


def _deliver(user_id: str, subscriptions: list, event: str, url: str, fields: dict):
    try:
        dao_subs = DAOPushSubscriptions()
        user = DAOUsers().get_users(user_id=user_id)
        lang = "vi" if user and user.get("preferred_language") == "Tiếng Việt" else "en"
        title, body = _message(event, lang, fields)
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
        logger.exception(f"push_service - _deliver failed for user {user_id}, event {event}: {repr(e)}")
