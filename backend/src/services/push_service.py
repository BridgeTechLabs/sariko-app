import json
import logging
import os
import threading

from pywebpush import webpush, WebPushException

from dao.dao_push_subscriptions import DAOPushSubscriptions
from dao.dao_users import DAOUsers
from services import zalo

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
    "payment_confirmed": {
        "en": ("Payment confirmed", "VNPay confirmed your payment. Your order is with the seller."),
        "vi": ("Đã xác nhận thanh toán", "VNPay đã xác nhận thanh toán. Đơn hàng đã được gửi tới người bán."),
    },
    "payment_failed": {
        "en": ("Payment not completed", "VNPay did not take the payment for your order. You can pay again."),
        "vi": ("Thanh toán không thành công", "VNPay không ghi nhận thanh toán cho đơn hàng. Bạn có thể thanh toán lại."),
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
    # T176 A4: an admin cancelled the order (Admin Gateway, apis/admin_gateway.py)
    "admin_cancelled_paid": {
        "en": ("Order cancelled", "Order #{code} was cancelled by Sariko. Your payment will be refunded."),
        "vi": ("Đơn hàng đã bị hủy", "Đơn #{code} đã bị Sariko hủy. Tiền sẽ được hoàn lại cho bạn."),
    },
    "admin_cancelled": {
        "en": ("Order cancelled", "Order #{code} was cancelled."),
        "vi": ("Đơn hàng đã bị hủy", "Đơn #{code} đã bị hủy."),
    },
    "seller_admin_cancelled": {
        "en": ("Order cancelled by Sariko", "Order #{code} was cancelled by Sariko. Tap to see details."),
        "vi": ("Sariko đã hủy đơn", "Đơn #{code} đã bị Sariko hủy. Nhấn để xem chi tiết."),
    },
    "seller_admin_cancelled_done": {
        "en": ("Order cancelled by Sariko", "Order #{code} was cancelled by Sariko and does not count in your earnings."),
        "vi": ("Sariko đã hủy đơn", "Đơn #{code} đã bị Sariko hủy, không tính vào thu nhập."),
    },
    "seller_admin_cancelled_charged": {
        "en": ("Order cancelled by Sariko", "Order #{code} was cancelled by Sariko. Its amount will be taken from your next payout."),
        "vi": ("Sariko đã hủy đơn", "Đơn #{code} đã bị Sariko hủy, số tiền của đơn sẽ được trừ ở kỳ chi trả tới."),
    },
    "admin_order_expiring": {
        "en": ("Order #{code} not accepted", "{minutes} min left before it auto-cancels. Call the seller."),
        "vi": ("Đơn #{code} chưa được nhận", "Còn {minutes} phút trước khi tự hủy. Hãy gọi người bán."),
    },
    "admin_delivery_failed": {
        "en": ("Order #{code}: delivery failed", "The delivery company could not deliver it. Tap to open the order."),
        "vi": ("Đơn #{code} giao thất bại", "Hãng giao hàng không giao được. Nhấn để mở đơn."),
    },
    "admin_delivery_lost": {
        "en": ("Order #{code}: food lost on the way", "Lost, damaged or sent back after pickup. Contact the buyer and the seller."),
        "vi": ("Đơn #{code} thất lạc khi giao", "Hàng mất, hỏng hoặc bị trả lại sau khi lấy. Hãy liên hệ người mua và người bán."),
    },
    "admin_delivery_wallet_empty": {
        "en": ("Delivery wallet is empty", "No rider booked for order #{code}. Top up the delivery wallet."),
        "vi": ("Ví giao hàng hết tiền", "Chưa đặt được xe cho đơn #{code}. Hãy nạp tiền vào ví giao hàng."),
    },
    "admin_delivery_wallet_low": {
        "en": ("Delivery wallet running low", "AllinGo wallet: {balance} (alert below {threshold}). Top up before trips start failing."),
        "vi": ("Ví giao hàng sắp hết tiền", "Ví AllinGo còn {balance} (báo khi dưới {threshold}). Hãy nạp tiền trước khi đặt xe bị lỗi."),
    },
}

# The same admin events in the team's Zalo groups (T136): kind + English text (Q4), {category} translated like above.
ZALO_ADMIN = {
    "admin_new_complaint": ("support", "📣 New complaint {code} · {category}"),
    "admin_order_expiring": ("ops", "⏰ Order #{code} not accepted by the seller, auto-cancels in {minutes} min. Call the seller."),
    "admin_delivery_failed": ("ops", "🚚 Order #{code}: delivery failed, the delivery company could not deliver it."),
    "admin_delivery_lost": ("ops", "📦 Order #{code}: food lost, damaged or sent back after pickup. Contact the buyer and the seller."),
    "admin_delivery_wallet_empty": ("ops", "💸 Delivery wallet is empty: no rider booked for order #{code}. Top up the wallet."),
    "admin_delivery_wallet_low": ("ops", "🪫 AllinGo wallet low: {balance} (alert below {threshold}). Top up before trips start failing."),
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
    """Seller side: the delivery company assigned a driver (again, if the first one cancelled). Called from the webhooks."""
    _send_async(order.get("seller_user_id"), "seller_driver_assigned", f"/seller/orders/{order['id']}")


def notify_seller_delivered(order: dict):
    """Seller side: Lalamove reported the delivery COMPLETED.
    Called from the webhook — a seller marking 'done' themselves needs no push."""
    _send_async(order.get("seller_user_id"), "seller_delivered", f"/seller/orders/{order['id']}")


def notify_payment_confirmed(order: dict):
    """Buyer side: the reconcile job found the payment at VNPay after the IPN did not come (T125)."""
    _send_async(order.get("user_id"), "payment_confirmed", f"/orders/{order['id']}")


def notify_payment_failed(order: dict):
    """Buyer side: VNPay says the pay link was not paid; once per link (T125)."""
    _send_async(order.get("user_id"), "payment_failed", f"/orders/{order['id']}")


def notify_seller_complaint(seller_user_id, order_id: str):
    """Seller side: the buyer filed a complaint about this order (T35)."""
    _send_async(seller_user_id, "seller_complaint", f"/seller/orders/{order_id}")


def notify_admin_cancelled(order: dict, was_done: bool, charged: bool):
    """T176 A4: an admin cancelled the order. Buyer: refunded if paid. Seller (paid orders only, the others never reached
    them): a done order with a "Charge to seller" deduction is taken from the next payout; a done order not paid out yet
    does not count; otherwise (not done, or paid out with Sariko covering the refund) no money words."""
    code = order["id"][:8].upper()
    paid = order.get("payment_status") == "paid"
    _send_async(order.get("user_id"), "admin_cancelled_paid" if paid else "admin_cancelled", f"/orders/{order['id']}", code=code)
    if not paid:
        return
    event = ("seller_admin_cancelled_charged" if charged else
             "seller_admin_cancelled_done" if was_done and order.get("payout_status") in (None, "pending") else
             "seller_admin_cancelled")
    _send_async(order.get("seller_user_id"), event, f"/seller/orders/{order['id']}", code=code)


def notify_admins(event: str, url: str, **fields):
    """Admin panel: every admin-app subscription gets it (no admin roles), and the team's Zalo group.
    url is an admin-panel path."""
    try:
        if event in ZALO_ADMIN:
            kind, text = ZALO_ADMIN[event]
            f = {**fields, "code": str(fields.get("code", "")).upper()}
            if "category" in f:
                f["category"] = COMPLAINT_CATEGORIES.get(f["category"], {}).get("en", f["category"])
            zalo.send(kind, f"{text.format(**f)}\n{zalo.link(url)}")
    except Exception as e:
        logger.error(f"[Zalo] {event} message skipped: {type(e).__name__}")
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


def _send_async(user_id, event: str, url: str, **fields):
    # Push services can take seconds to answer; never hold up the request
    # (or the VNPay IPN) that changed the order.
    if not user_id or not VAPID_PRIVATE_KEY:
        return
    threading.Thread(target=_send, args=(user_id, event, url, fields), daemon=True).start()


def _send(user_id: str, event: str, url: str, fields: dict):
    try:
        subscriptions = DAOPushSubscriptions().read_subscriptions_by_user_id(user_id)
        if subscriptions:
            _deliver(user_id, subscriptions, event, url, fields)
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
