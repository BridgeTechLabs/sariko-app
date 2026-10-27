"""Ops messages to the team's Zalo groups (docs/dev/zalo-alerts, T136) through the Zalo Bot API, standard library only.
One chat id per kind (ZALO_CHAT_ORDERS / _SUPPORT / _OPS); no ZALO_BOT_TOKEN or no chat id for the kind = nothing is
sent (DEV / local default). Sent in a background thread with a 10 s timeout: an error is one log line and never
reaches the request, IPN or job that sent it. Env is read on each call. Never put buyer names, phones or addresses
or seller bank accounts in a message."""
import json
import logging
import os
import threading
import urllib.request
from datetime import datetime
from decimal import Decimal

from core.store_hours import VN_TZ

logger = logging.getLogger(__name__)

CHATS = {"orders": "ZALO_CHAT_ORDERS", "support": "ZALO_CHAT_SUPPORT", "ops": "ZALO_CHAT_OPS"}
TIMEOUT_SECONDS = 10
MAX_TEXT = 2000   # Bot API limit

REFUND_REASONS = {
    "buyer_cancel": "Người mua huỷ", "driver_booking_failed": "Không đặt được tài xế", "seller_cancel": "Quán huỷ",
    "seller_timeout": "Quán không nhận đơn kịp", "admin_cancel": "Admin huỷ",
    "late_payment": "Trả tiền sau khi đơn đã huỷ", "duplicate_payment": "Trả tiền 2 lần", "sold_out": "Hết suất",
}

def configured(kind: str) -> bool:
    return bool(os.getenv("ZALO_BOT_TOKEN") and os.getenv(CHATS[kind]))


def send(kind: str, text: str) -> None:
    if not configured(kind):
        return
    env = os.getenv("ENV", "local")
    if env != "prd":
        text = f"[TEST {env.upper()}] {text}"
    threading.Thread(target=_post, args=(os.getenv("ZALO_BOT_TOKEN"), os.getenv(CHATS[kind]), text[:MAX_TEXT]),
                     daemon=True).start()


def _post(token: str, chat_id: str, text: str) -> None:
    try:
        req = urllib.request.Request(f"https://bot-api.zaloplatforms.com/bot{token}/sendMessage",
                                     data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            body = json.load(res)
        if not body.get("ok"):
            logger.error(f"[Zalo] not sent: {body.get('error_code')} {body.get('description')}")
    except Exception as e:   # the token is in the URL: log the error type only
        logger.error(f"[Zalo] not sent: {type(e).__name__} {getattr(e, 'code', '')}".rstrip())


def link(path: str) -> str:
    return f"{(os.getenv('ADMIN_APP_URL') or 'https://admin.sariko.store').rstrip('/')}{path}"


def vnd(amount) -> str:
    return f"{int(Decimal(str(amount)).quantize(Decimal(1))):,}".replace(",", ".") + " ₫"


def new_order_text(order: dict) -> str:
    store = (order.get("seller_profiles") or {}).get("store_name") or ""
    when = order.get("delivery_appointment")
    when = f"Hẹn {datetime.fromisoformat(when).astimezone(VN_TZ):%d/%m %H:%M}" if when else "Giao ngay"
    url = link(f"/orders?open={order['id']}")
    return f"🛒 Đơn mới #{order['id'][:8].upper()} · {store} · {vnd(order['total_amount'])} · {when}\n{url}"


def refund_text(refund: dict) -> str:
    return (f"💸 Hoàn tiền chờ xử lý · đơn #{refund['order_id'][:8].upper()} · {vnd(refund['amount'])} · "
            f"{REFUND_REASONS.get(refund['reason'], refund['reason'])}\n{link('/refunds')}")
