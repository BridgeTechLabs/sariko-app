"""T125: ask VNPay (querydr) what happened to an unpaid order's current pay link, when the IPN is late or
never comes (docs/dev/payment-confirm/README.md). Used by the reconcile job and before a new pay link.

VNPay answers 94 "Request is duplicated" when the same transaction is asked again within ~15 minutes, so
each link is asked at most once per QUERY_GAP; the last signed answer is kept on the order and reused in
between. Orders with a refund are never asked: querydr by TxnRef keeps answering "paid" after a refund.
Request / response checksums: VNPay online docs, as in the admin app's refunds.py (same field orders)."""
import hashlib
import hmac
import logging
import os
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import cache
from typing import Optional

import requests

logger = logging.getLogger(__name__)

VN_TZ = timezone(timedelta(hours=7))
QUERY_GAP = timedelta(minutes=15)       # VNPay protocol limit (94 within ~15 min), not a business parameter
LINK_LIFETIME = timedelta(minutes=15)   # vnp_ExpireDate of a pay link, set in apis/payments.py create

VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE", "")
VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET", "")
# merchant_webapi (querydr). Unset: the API of the same VNPay environment as the pay page (VNPAY_URL).
VNPAY_API_URL = os.getenv("VNPAY_API_URL") or (
    "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction"
    if "sandbox" in os.getenv("VNPAY_URL", "sandbox") else "https://merchant.vnpay.vn/merchant_webapi/api/transaction")
# vnp_IpAddr = IP of the server calling the API. Set it to the EC2 public IP (inside Docker the outgoing
# interface is private); unset, the outgoing interface is used, as in the admin app.
VNPAY_SERVER_IP = os.getenv("VNPAY_SERVER_IP", "")

# querydr answer checksum, in this exact order
RESPONSE_FIELDS = [
    "vnp_ResponseId", "vnp_Command", "vnp_ResponseCode", "vnp_Message", "vnp_TmnCode", "vnp_TxnRef",
    "vnp_Amount", "vnp_BankCode", "vnp_PayDate", "vnp_TransactionNo", "vnp_TransactionType",
    "vnp_TransactionStatus", "vnp_OrderInfo", "vnp_PromotionCode", "vnp_PromotionAmount",
]
KEPT = ("vnp_TxnRef", "vnp_Amount", "vnp_ResponseCode", "vnp_Message", "vnp_TransactionType",
        "vnp_TransactionStatus", "vnp_TransactionNo", "vnp_BankCode", "vnp_PayDate")


class QuerydrSignatureError(Exception):
    """querydr answered 00 with a vnp_SecureHash that doesn't match: not from VNPay, ignore it."""


def _hash(fields: list) -> str:
    return hmac.new(VNPAY_HASH_SECRET.encode(), "|".join(fields).encode(), hashlib.sha512).hexdigest()


@cache
def _server_ip() -> str:
    if VNPAY_SERVER_IP:
        return VNPAY_SERVER_IP
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:   # sends nothing: picks the outgoing interface
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def _post(payload: dict) -> dict:
    """The one HTTP call to VNPay. Stubbed in tests."""
    resp = requests.post(VNPAY_API_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def querydr(txn_ref: str, transaction_date: str, order_id: str) -> dict:
    request_id = uuid.uuid4().hex[:16].upper()
    create_date = datetime.now(VN_TZ).strftime("%Y%m%d%H%M%S")
    order_info = f"Tra cuu don hang {order_id[:8]}"
    ip = _server_ip()
    payload = {
        "vnp_RequestId": request_id, "vnp_Version": "2.1.0", "vnp_Command": "querydr",
        "vnp_TmnCode": VNPAY_TMN_CODE, "vnp_TxnRef": txn_ref, "vnp_OrderInfo": order_info,
        "vnp_TransactionDate": transaction_date, "vnp_CreateDate": create_date, "vnp_IpAddr": ip,
        "vnp_SecureHash": _hash([request_id, "2.1.0", "querydr", VNPAY_TMN_CODE, txn_ref,
                                 transaction_date, create_date, ip, order_info]),
    }
    resp = _post(payload)
    if resp.get("vnp_ResponseCode") == "00":
        data = ["" if resp.get(k) is None else str(resp[k]) for k in RESPONSE_FIELDS]
        if not hmac.compare_digest(_hash(data).lower(), str(resp.get("vnp_SecureHash") or "").lower()):
            raise QuerydrSignatureError(f"querydr checksum mismatch for {txn_ref}")
    return resp


def current_txn(order: dict) -> Optional[tuple]:
    """(vnp_TxnRef, link made at) of the order's last pay link, or None (no link, or an old-style ref)."""
    created = order.get("payment_create_date") or ""
    if not re.fullmatch(r"\d{14}", created):
        return None
    return f"{order['id'].replace('-', '')}_{created}", datetime.strptime(created, "%Y%m%d%H%M%S").replace(tzinfo=VN_TZ)


def ipn_result(order: dict, txn_ref: str) -> Optional[str]:
    """'succeeded' / 'failed' when the IPN already reported this link (payments row), else None."""
    rows = [p for p in order.get("payments") or [] if p.get("transaction_ref") == txn_ref]
    return rows[0]["status"] if rows else None


def classify(check: dict, total_amount, link_made_at: datetime, now: datetime) -> str:
    """paid | pending | failed | unknown for a kept querydr answer.
    unknown (other codes, fraud suspicion 07, amount mismatch): never marked paid nor failed."""
    code, status = check.get("vnp_ResponseCode"), check.get("vnp_TransactionStatus")
    expired = now > link_made_at + LINK_LIFETIME
    if code == "00" and status == "00" and check.get("vnp_TransactionType") == "01":
        if str(check.get("vnp_Amount")) == str(int(Decimal(str(total_amount)) * 100)):
            return "paid"
        logger.error(f"[VNPay check] {check.get('vnp_TxnRef')}: paid {check.get('vnp_Amount')}, order total {total_amount}")
        return "unknown"
    if code == "00" and status in ("02", "04"):   # error / reversed: not taken by VNPay
        return "failed"
    if (code == "00" and status == "01") or code == "91":   # not completed / transaction not found
        return "failed" if expired else "pending"
    return "unknown"


def check_order(order: dict, dao, now: datetime) -> tuple:
    """(outcome, kept answer) for the order's current pay link, asking VNPay only if the last answer is
    older than QUERY_GAP. outcome: none (no link / refund / IPN already answered) or classify()'s."""
    txn = current_txn(order)
    if not txn or order.get("refunds") or ipn_result(order, txn[0]):
        return "none", None
    txn_ref, made_at = txn
    check, checked_at = order.get("vnpay_check"), order.get("vnpay_checked_at")
    fresh = check and check.get("vnp_TxnRef") == txn_ref and checked_at \
        and now - datetime.fromisoformat(checked_at) < QUERY_GAP
    if not fresh:
        if not dao.claim_vnpay_check(order["id"], now, now - QUERY_GAP):
            return "unknown", check   # someone else is asking VNPay right now
        order["vnpay_checked_at"] = now.isoformat()
        resp = querydr(txn_ref, order["payment_create_date"], order["id"])
        logger.warning(f"[VNPay check] order={order['id']} txn={txn_ref} code={resp.get('vnp_ResponseCode')} "
                       f"type={resp.get('vnp_TransactionType')} status={resp.get('vnp_TransactionStatus')}")
        if resp.get("vnp_ResponseCode") == "94":   # asked too soon: keep the last real answer
            return "unknown", check
        check = {k: resp.get(k) for k in KEPT} | {"vnp_TxnRef": txn_ref}
        dao.save_vnpay_check(order["id"], check, now)
        order["vnpay_check"] = check
    if not check:
        return "unknown", None
    return classify(check, order["total_amount"], made_at, now), check


def retry_at(order: dict) -> datetime:
    """When the next check can say more: the link expired and VNPay accepts a new query."""
    made_at = current_txn(order)[1]
    checked = order.get("vnpay_checked_at")
    last = datetime.fromisoformat(checked) if checked else made_at
    return max(made_at + LINK_LIFETIME, last + QUERY_GAP)
