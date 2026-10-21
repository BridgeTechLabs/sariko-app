import os
import hmac
import hashlib
import urllib.parse
import logging
from decimal import Decimal
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse

from core.auth import verify_token
from core.client_ip import client_ip
from dao.dao_orders import DAOOrders
from dao.dao_payments import DAOPayments
from dao.dao_refunds import DAORefunds

router = APIRouter(prefix="/payments")
logger = logging.getLogger(__name__)

# VNPay config from env
VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE", "YOUR_TMN_CODE")
VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET", "YOUR_HASH_SECRET")
VNPAY_URL = os.getenv("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNPAY_RETURN_URL = os.getenv("VNPAY_RETURN_URL", "http://localhost:8081/payment/return")


def _hmac_sha512(key: str, data: str) -> str:
    return hmac.new(key.encode('utf-8'), data.encode('utf-8'), hashlib.sha512).hexdigest()


def _build_vnpay_url(params: dict) -> str:
    """Sort params alphabetically, URL encode keys and values, hash, append to VNPay URL.
    The hash data and the query string are the same URL-encoded string (as in VNPay's online
    docs and demo code; the old v2.1.0 PDF said raw values)."""
    # Filter empty values
    filtered = {k: v for k, v in params.items() if v is not None and v != ''}

    # Sort by key alphabetically
    sorted_params = sorted(filtered.items())

    # Build hash data: key=value&key2=value2 (values URL encoded per US-ASCII)
    hash_data = '&'.join(
        f"{urllib.parse.quote_plus(str(k), safe='')}"
        f"={urllib.parse.quote_plus(str(v), safe='')}"
        for k, v in sorted_params
    )

    # Build query string (same encoding)
    query_string = hash_data

    # Create HMAC SHA512 hash
    secure_hash = _hmac_sha512(VNPAY_HASH_SECRET, hash_data)

    return f"{VNPAY_URL}?{query_string}&vnp_SecureHash={secure_hash}"


def _order_id_from_txn_ref(txn_ref: str) -> str:
    """"<32 hex>_<yyyyMMddHHmmss>" (or the older "<32 hex>_<HHmmss>") -> order UUID, or ""."""
    hex_id = (txn_ref or "").split("_")[0]
    if len(hex_id) != 32:
        return ""
    return f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}"


def _refund_extra_payment(order: dict, params: dict, txn_ref: str, reason: str) -> JSONResponse:
    """VNPay took money the order must not keep, so queue a full refund of it for the admin
    and ack so VNPay stops retrying. Never changes the order.
      late_payment: the order no longer waited for payment (cancelled while the buyer paid).
      duplicate_payment: a second payment (another TxnRef) for an order already paid, or a
        second late payment; it gets its own refund next to the order's main one.
    A VNPay retry of the same IPN finds its TxnRef among the refunds and gets RspCode 02."""
    order_id = order["id"]
    suffix = txn_ref.rsplit("_", 1)[-1]
    amount = int(Decimal(params["vnp_Amount"]) / 100)   # this payment, VND (checked = order total)
    try:
        refunds = DAORefunds()
        known = refunds.read_txn_refs(order_id)
        if txn_ref in known:
            logger.warning(f"VNPay IPN: {txn_ref} of order {order_id} already queued for refund")
            return JSONResponse(content={"RspCode": "02", "Message": "Order already confirmed"})
        if reason == "late_payment" and known:   # the order already has its main refund
            reason = "duplicate_payment"
        refund = refunds.create_refund(
            order_id=order_id,
            amount=amount,
            reason=reason,
            original_txn_ref=txn_ref,
            ipn_data=params,
            # the date the admin must send as vnp_TransactionDate (None for an old-style ref)
            payment_create_date=suffix if len(suffix) == 14 else None,
        )
    except Exception as e:
        if "23505" in str(e) or "duplicate key" in str(e):   # the same IPN racing itself
            logger.warning(f"VNPay IPN: {txn_ref} of order {order_id} already queued for refund")
            return JSONResponse(content={"RspCode": "02", "Message": "Order already confirmed"})
        logger.error(f"VNPay IPN: could not queue the {reason} refund for order {order_id}: {type(e).__name__}")
        return JSONResponse(content={"RspCode": "99", "Message": "Unknown error"})
    try:
        DAOPayments().create_payment(
            order_id=order_id, method="vnpay", amount=amount,
            status="succeeded", transaction_ref=txn_ref, type="charge",
            vnp_transaction_no=params.get("vnp_TransactionNo"),
        )
    except Exception as e:   # the refund (with the IPN data) is what matters; keep the ack
        logger.error(f"VNPay IPN: late payment row not saved for order {order_id}: {type(e).__name__}")
    logger.warning(f"VNPay IPN: {reason}: order {order_id} ({order.get('status')}, {order.get('payment_status')}) unchanged, "
                   f"refund {(refund or {}).get('id')} queued, txn_ref={txn_ref}")
    return JSONResponse(content={"RspCode": "00", "Message": "Confirm Success"})


@router.post("/vnpay/create/{order_id}")
def create_vnpay_payment(order_id: str, request: Request, user=Depends(verify_token)):
    """Create VNPay payment URL for an order."""

    # Get order
    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["payment_status"] == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    # The buyer's IP (VNPay: "Địa chỉ IP của khách hàng"), not nginx's
    ip = client_ip(request)

    # Timestamps (GMT+7)
    now = datetime.utcnow() + timedelta(hours=7)
    create_date = now.strftime("%Y%m%d%H%M%S")
    expire_date = (now + timedelta(minutes=15)).strftime("%Y%m%d%H%M%S")

    # Unique txn ref: full order UUID (no dashes) + vnp_CreateDate. A refund / querydr must
    # send this URL's vnp_CreateDate as vnp_TransactionDate; the admin app reads it from here.
    # Refs made before 2026-10-20 end in HHMMSS only (the admin falls back to payment_create_date).
    order_id_nodash = order["id"].replace("-", "")
    txn_ref = f"{order_id_nodash}_{create_date}"

    # Amount × 100 (VNPay requirement). Use Decimal to avoid float precision drift.
    amount = int(Decimal(str(order["total_amount"])) * 100)

    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": VNPAY_TMN_CODE,
        "vnp_Amount": str(amount),
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": f"Thanh toan don hang Sariko {order_id_nodash[:8]}",
        "vnp_OrderType": "other",   # sample value in VNPay's online docs; Jack is asking VNPay for our category
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": VNPAY_RETURN_URL,
        "vnp_IpAddr": ip,
        "vnp_CreateDate": create_date,
        "vnp_ExpireDate": expire_date,
        "vnp_CurrCode": "VND",
    }
    # No vnp_IpnUrl: it is not a v2.1.0 pay param, VNPay leaves it out of its hash check
    # and answers "Sai chữ ký" (code 70). The IPN URL is registered on the merchant portal.

    payment_url = _build_vnpay_url(params)
    # QA checks this on DEV: the buyer's public IP, never nginx's 172.x / 127.x
    logger.warning(f"VNPay pay URL: order {order_id}, txn_ref={txn_ref}, vnp_IpAddr={ip}")
    dao_orders.update_payment_create_date(order_id=order_id, payment_create_date=create_date)

    return {"success": True, "payment_url": payment_url}


@router.get("/vnpay/ipn")
def vnpay_ipn(request: Request):
    """IPN callback from VNPay (server-to-server). Verify hash and update payment status."""

    params = dict(request.query_params)

    # Extract and remove secure hash
    vnp_secure_hash = params.pop("vnp_SecureHash", "")
    params.pop("vnp_SecureHashType", None)

    # Rebuild hash from remaining params (same encoding as create)
    sorted_params = sorted(params.items())
    hash_data = '&'.join(
        f"{urllib.parse.quote_plus(str(k), safe='')}"
        f"={urllib.parse.quote_plus(str(v), safe='')}"
        for k, v in sorted_params
    )
    computed_hash = _hmac_sha512(VNPAY_HASH_SECRET, hash_data)

    # Verify hash (constant-time compare to prevent timing attacks)
    if not hmac.compare_digest(computed_hash, vnp_secure_hash):
        logger.warning(f"VNPay IPN hash mismatch")
        return JSONResponse(content={"RspCode": "97", "Message": "Invalid Checksum"})

    # Check response code
    response_code = params.get("vnp_ResponseCode", "")
    transaction_status = params.get("vnp_TransactionStatus", "")
    txn_ref = params.get("vnp_TxnRef", "")

    order_id = _order_id_from_txn_ref(txn_ref)

    if not order_id:
        logger.warning(f"VNPay IPN: Could not extract order_id from txn_ref={txn_ref}")
        return JSONResponse(content={"RspCode": "01", "Message": "Order not found"})

    # Look up order in DB
    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id_raw(order_id=order_id)
    if not order:
        logger.warning(f"VNPay IPN: Order not found for id={order_id}")
        return JSONResponse(content={"RspCode": "01", "Message": "Order not found"})

    # Validate amount: vnp_Amount is in VND × 100, order total_amount is in VND
    vnp_amount = int(params.get("vnp_Amount", "0"))
    expected_amount = int(Decimal(str(order["total_amount"])) * 100)
    if vnp_amount != expected_amount:
        logger.warning(f"VNPay IPN: Amount mismatch for order {order_id}. vnp_Amount={vnp_amount}, expected={expected_amount}")
        return JSONResponse(content={"RspCode": "04", "Message": "Invalid amount"})

    paid_now = response_code == "00" and transaction_status == "00"

    # Already paid: the same TxnRef is VNPay retrying; another one is a second payment (the
    # buyer opened two payment URLs) that must be refunded. Orders paid before transaction_ref
    # was recorded can't tell the two apart: answered as before.
    if order.get("payment_status") == "paid":
        if paid_now and order.get("transaction_ref") and txn_ref != order["transaction_ref"]:
            return _refund_extra_payment(order, params, txn_ref, "duplicate_payment")
        logger.warning(f"VNPay IPN: Order {order_id} already paid, skipping")
        return JSONResponse(content={"RspCode": "02", "Message": "Order already confirmed"})

    if paid_now and order.get("status") != "pending":
        return _refund_extra_payment(order, params, txn_ref, "late_payment")

    if response_code == "00" and transaction_status == "00":
        # Payment successful — update status
        try:
            dao_orders.update_payment_status(order_id=order_id, payment_status="paid", transaction_ref=txn_ref)
            dao_orders.update_ipn_data(order_id=order_id, ipn_data=params)
            DAOPayments().create_payment(
                order_id=order_id,
                method="vnpay",
                amount=Decimal(str(order["total_amount"])),
                status="succeeded",
                transaction_ref=txn_ref,
                type="charge",
                vnp_transaction_no=params.get("vnp_TransactionNo"),
            )
            logger.warning(f"VNPay IPN: Payment success for order_id={order_id}, txn_ref={txn_ref}")
            return JSONResponse(content={"RspCode": "00", "Message": "Confirm Success"})
        except Exception as e:
            logger.warning(f"VNPay IPN: Failed to update order: {e}")
            return JSONResponse(content={"RspCode": "99", "Message": "Unknown error"})
    else:
        # VNPay reports failure (insufficient funds, wrong OTP, customer cancelled, ...).
        # Per VNPay SIT test "Giao dịch không thành công" we ack with RspCode "00"
        # so VNPay stops retrying. We log the failed transaction in the payments table
        # (audit trail) but DO NOT change order.payment_status — it stays "pending"
        # so the user can retry payment from the order detail page.
        try:
            DAOPayments().create_payment(
                order_id=order_id,
                method="vnpay",
                amount=Decimal(str(order["total_amount"])),
                status="failed",
                transaction_ref=txn_ref,
                type="charge",
                vnp_transaction_no=params.get("vnp_TransactionNo"),
            )
            dao_orders.update_ipn_data(order_id=order_id, ipn_data=params)
        except Exception as e:
            logger.warning(f"VNPay IPN: Failed to record failed transaction: {e}")
            return JSONResponse(content={"RspCode": "99", "Message": "Unknown error"})
        logger.warning(f"VNPay IPN: Payment failed. ResponseCode={response_code}, TxnRef={txn_ref}")
        return JSONResponse(content={"RspCode": "00", "Message": "Confirm Success"})


@router.get("/vnpay/return")
def vnpay_return(request: Request):
    """Return URL — browser redirect after payment. Only for display, NOT for updating DB."""

    params = dict(request.query_params)

    vnp_secure_hash = params.pop("vnp_SecureHash", "")
    params.pop("vnp_SecureHashType", None)

    sorted_params = sorted(params.items())
    hash_data = '&'.join(
        f"{urllib.parse.quote_plus(str(k), safe='')}"
        f"={urllib.parse.quote_plus(str(v), safe='')}"
        for k, v in sorted_params
    )
    computed_hash = _hmac_sha512(VNPAY_HASH_SECRET, hash_data)

    is_valid = hmac.compare_digest(computed_hash, vnp_secure_hash)
    response_code = params.get("vnp_ResponseCode", "")
    txn_ref = params.get("vnp_TxnRef", "")

    # order_id for the frontend polling
    order_id = _order_id_from_txn_ref(txn_ref)

    return {
        "success": is_valid and response_code == "00",
        "response_code": response_code,
        "txn_ref": txn_ref,
        "order_id": order_id,
        "is_valid": is_valid
    }


@router.get("/payment-status/{order_id}")
def get_payment_status(order_id: str, user=Depends(verify_token)):
    """Poll payment status from DB. Used by payment return page after VNPay redirect."""
    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return {
        "payment_status": order["payment_status"],
    }
