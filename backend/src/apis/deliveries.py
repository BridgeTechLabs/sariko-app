import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, HTTPException, Depends, Request

from core.auth import verify_token
from core.phone import to_e164_vn
from dao.dao_deliveries import DAODeliveries
from dao.dao_orders import DAOOrders
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from services.lalamove_service import get_lalamove_service

router = APIRouter(prefix="/deliveries")
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# POST /deliveries/quotation — get delivery fee estimate
# --------------------------------------------------------------------------
@router.post("/quotation")
def get_quotation(body: Schema.RequestQuotation, user=Depends(verify_token)):
    try:
        dao_sellers = DAOSellerProfiles()
        seller = dao_sellers.read_seller_coords_by_id(body.seller_id)
        if not seller:
            raise HTTPException(status_code=404, detail="Seller not found")

        seller_lat = seller.get("lat")
        seller_lon = seller.get("lon")
        if not seller_lat or not seller_lon:
            raise HTTPException(status_code=400, detail="Seller location not configured")

        service = get_lalamove_service()
        result = service.get_quotation(
            pickup_lat=float(seller_lat),
            pickup_lon=float(seller_lon),
            pickup_address=seller.get("address") or "Pickup",
            dropoff_lat=body.delivery_lat,
            dropoff_lon=body.delivery_lon,
            dropoff_address=body.delivery_address,
        )

        return {
            "success": True,
            "quotation_id": result.quotation_id,
            "stop_id_0": result.stop_id_0,
            "stop_id_1": result.stop_id_1,
            "total_fee": result.total_fee,
            "currency": result.currency,
            "distance_km": result.distance_km,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /deliveries/quotation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# GET /deliveries/{order_id}/status — read delivery status from DB (buyer)
# Webhook updates the DB; frontend uses Supabase realtime — no Lalamove API call needed here
# --------------------------------------------------------------------------
@router.get("/{order_id}/status")
def get_delivery_status(order_id: str, user=Depends(verify_token)):
    try:
        dao_orders = DAOOrders()
        order = dao_orders.read_order_by_id(order_id, user["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_order_id(order_id)
        if not delivery:
            return {"success": True, "delivery": None}

        return {
            "success": True,
            "delivery": {
                "status": delivery.get("status"),
                "driver_name": delivery.get("driver_name"),
                "driver_phone": delivery.get("driver_phone"),
                "driver_plate": delivery.get("driver_plate"),
                "tracking_url": delivery.get("tracking_url"),
                "share_link": delivery.get("share_link"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /deliveries/{order_id}/status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# POST /deliveries/webhook — Lalamove status callback (public, v3)
# --------------------------------------------------------------------------
@router.post("/webhook")
async def delivery_webhook(request: Request):
    try:
        # Read raw bytes first — needed for exact HMAC verification
        raw_body = await request.body()
        body = json.loads(raw_body)

        api_key    = body.get("apiKey", "")
        timestamp  = body.get("timestamp", 0)
        signature  = body.get("signature", "")
        event_type = body.get("eventType", "")
        data       = body.get("data", {})

        # Signature validation — fail-closed: missing secret means we cannot verify, so reject.
        api_secret = os.getenv("LALAMOVE_API_SECRET", "")
        api_key_env = os.getenv("LALAMOVE_API_KEY", "")
        if not api_secret or not api_key_env:
            logger.error("Webhook: LALAMOVE_API_SECRET/API_KEY not configured — rejecting")
            raise HTTPException(status_code=503, detail="Webhook not configured")

        if api_key != api_key_env:
            logger.warning(f"Webhook: apiKey mismatch ({api_key[:10]}...)")
            raise HTTPException(status_code=401, detail="Invalid apiKey")

        # Extract the raw "data" value from the original body bytes
        # so we sign exactly what Lalamove signed (no re-serialization risk)
        raw_str   = raw_body.decode("utf-8")
        data_start = raw_str.index('"data"') + len('"data"')
        # skip whitespace and ':'
        i = data_start
        while i < len(raw_str) and raw_str[i] in ' \t\r\n:':
            i += 1
        # extract balanced JSON object/array
        depth, in_str, escape = 0, False, False
        start = i
        while i < len(raw_str):
            c = raw_str[i]
            if escape:
                escape = False
            elif c == '\\' and in_str:
                escape = True
            elif c == '"':
                in_str = not in_str
            elif not in_str:
                if c in '{[':
                    depth += 1
                elif c in '}]':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        raw_data_str = raw_str[start:i + 1]

        path = request.url.path
        raw  = f"{timestamp}\r\nPOST\r\n{path}\r\n\r\n{raw_data_str}"
        expected = hmac.new(api_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning(f"Webhook: signature mismatch. path={path}")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # v3 payload: data.order holds the order fields
        order_data  = data.get("order", {})
        driver_data = data.get("driver", {})

        lalamove_order_id = order_data.get("orderId")
        new_status        = order_data.get("status")

        if (not event_type == 'DRIVER_ASSIGNED') and (not lalamove_order_id or not new_status):
            logger.warning(f"Webhook: missing orderId or status in payload (eventType={event_type})")
            return {"success": True}  # 200 so Lalamove doesn't retry malformed events

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_lalamove_order_id(lalamove_order_id)
        if not delivery:
            logger.warning(f"Webhook: no delivery row for lalamove_order_id={lalamove_order_id}")
            return {"success": True}  # 200 — unknown order, don't retry

        TERMINAL_STATUSES = {"REJECTED", "CANCELLED", "CANCELED", "EXPIRED"}

        update_data = {}
        if new_status:
            update_data["status"] = new_status

        if new_status in TERMINAL_STATUSES:
            update_data["driver_name"] = None
            update_data["driver_phone"] = None
            update_data["driver_plate"] = None
            update_data["share_link"] = None
        else:
            # Driver info present in DRIVER_ASSIGNED and some ORDER_STATUS_CHANGED events
            if driver_data.get("name"):
                update_data["driver_name"] = driver_data["name"]
            if driver_data.get("phone"):
                update_data["driver_phone"] = driver_data["phone"]
            if driver_data.get("plateNumber"):
                update_data["driver_plate"] = driver_data["plateNumber"]
            if order_data.get("shareLink"):
                update_data["share_link"] = order_data["shareLink"]

        dao_deliveries.update_delivery(delivery["id"], update_data)
        logger.warning(f"[Webhook] {event_type} → order={lalamove_order_id} status={new_status}")

        dao_orders = DAOOrders()
        if new_status == "COMPLETED":
            dao_orders.update_order_status(delivery["order_id"], "done")
        elif new_status in TERMINAL_STATUSES:
            order = dao_orders.read_order_by_id_raw(delivery["order_id"])
            if order and order["status"] == "ready":
                dao_orders.update_order_status(delivery["order_id"], "delivery_failed")
                logger.warning(f"[Webhook] order={delivery['order_id']} → delivery_failed (lalamove={new_status})")

        return {"success": True}

    except HTTPException:
        # Auth/signature failures — propagate proper status to Lalamove
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /deliveries/webhook: {e}")
        # Still return 200 to avoid Lalamove retry storms on our own bugs
        return {"success": False, "detail": "Internal error"}


# --------------------------------------------------------------------------
# GET /deliveries/{order_id}/seller-status — seller reads delivery status
# --------------------------------------------------------------------------
@router.get("/{order_id}/seller-status")
def get_delivery_status_for_seller(order_id: str, user=Depends(verify_token)):
    try:
        dao_sellers = DAOSellerProfiles()
        profile = dao_sellers.read_seller_profile_by_user_id(user["id"])
        if not profile:
            raise HTTPException(status_code=403, detail="Not a seller")

        dao_orders = DAOOrders()
        order = dao_orders.read_order_by_id_for_seller(order_id, profile["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_order_id(order_id)
        if not delivery:
            return {"success": True, "delivery": None}

        return {
            "success": True,
            "delivery": {
                "status": delivery.get("status"),
                "driver_name": delivery.get("driver_name"),
                "driver_phone": delivery.get("driver_phone"),
                "driver_plate": delivery.get("driver_plate"),
                "share_link": delivery.get("share_link"),
                "rebook_count": delivery.get("rebook_count", 0),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /deliveries/{order_id}/seller-status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# POST /deliveries/{order_id}/rebook — seller re-books after Lalamove rejects
# --------------------------------------------------------------------------
@router.post("/{order_id}/rebook")
def rebook_delivery(order_id: str, user=Depends(verify_token)):
    try:
        dao_sellers = DAOSellerProfiles()
        profile = dao_sellers.read_seller_profile_by_user_id(user["id"])
        if not profile:
            raise HTTPException(status_code=403, detail="Not a seller")

        dao_orders = DAOOrders()
        order = dao_orders.read_order_by_id_for_seller(order_id, profile["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] not in ("ready", "delivery_failed") or order.get("delivery_method") != "delivery":
            raise HTTPException(status_code=400, detail="Order must be ready or delivery_failed with delivery method")

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_order_id(order_id)
        if not delivery or delivery["status"] not in ("CANCELLED", "CANCELED", "REJECTED", "EXPIRED"):
            raise HTTPException(status_code=400, detail="No cancelled delivery to rebook")

        rebook_count = delivery.get("rebook_count", 0)
        if rebook_count >= 3:
            raise HTTPException(status_code=400, detail="Max rebook attempts reached")

        full_order = dao_orders.read_order_with_seller_coords(order_id)
        if not full_order:
            raise HTTPException(status_code=500, detail="Could not load order details")

        seller  = full_order.get("seller_profiles") or {}
        buyer   = full_order.get("users") or {}
        service = get_lalamove_service()

        try:
            sender_phone = to_e164_vn(seller.get("phone") or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Seller phone invalid: {e}")
        try:
            recipient_phone = to_e164_vn(buyer.get("phone") or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Buyer phone invalid: {e}")

        quotation = service.get_quotation(
            pickup_lat=float(seller.get("lat") or 0),
            pickup_lon=float(seller.get("lon") or 0),
            pickup_address=seller.get("address", ""),
            dropoff_lat=float(full_order.get("delivery_lat") or 0),
            dropoff_lon=float(full_order.get("delivery_lon") or 0),
            dropoff_address=full_order.get("delivery_address", ""),
        )
        result = service.place_order(
            quotation_id=quotation.quotation_id,
            stop_id_0=quotation.stop_id_0,
            stop_id_1=quotation.stop_id_1,
            sender_name=seller.get("store_name", "Seller"),
            sender_phone=sender_phone,
            recipient_name=buyer.get("name") or buyer.get("email") or "Customer",
            recipient_phone=recipient_phone,
            recipient_remarks=full_order.get("delivery_address") or "",
        )

        try:
            dao_deliveries.update_delivery(delivery["id"], {
                "status": result.status,
                "lalamove_order_id": result.lalamove_order_id,
                "share_link": result.share_link or "",
                "driver_name": None,
                "driver_phone": None,
                "driver_plate": None,
                "rebook_count": rebook_count + 1,
            })
        except Exception as db_err:
            # DB write failed but Lalamove already booked — roll back to avoid orphan order.
            logger.error(f"[Delivery] DB update failed after rebook (lalamove={result.lalamove_order_id}); cancelling Lalamove order")
            try:
                service.cancel_order(result.lalamove_order_id)
            except Exception as cancel_err:
                logger.error(f"[Delivery] Rollback cancel also failed for {result.lalamove_order_id}: {cancel_err}")
            raise HTTPException(status_code=500, detail=f"Rebook DB update failed: {db_err}")

        if order["status"] == "delivery_failed":
            dao_orders.update_order_status(order_id, "ready")

        logger.warning(f"[Delivery] Re-booked order={order_id} attempt={rebook_count + 1} lalamove={result.lalamove_order_id}")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /deliveries/{order_id}/rebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# DELETE /deliveries/{order_id}/cancel — cancel delivery
# --------------------------------------------------------------------------
@router.delete("/{order_id}/cancel")
def cancel_delivery(order_id: str, user=Depends(verify_token)):
    try:
        dao_orders = DAOOrders()
        order = dao_orders.read_order_by_id(order_id, user["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_order_id(order_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="No delivery found for this order")

        # Already cancelled — idempotent no-op
        if delivery.get("status") in ("CANCELLED", "CANCELED", "REJECTED", "EXPIRED"):
            return {"success": True}

        # Don't allow cancel after pickup — driver is already en route with the food
        if delivery.get("status") == "PICKED_UP":
            raise HTTPException(status_code=409, detail="Driver has already picked up the order")

        service = get_lalamove_service()
        lalamove_order_id = delivery.get("lalamove_order_id")
        if lalamove_order_id:
            ok = service.cancel_order(lalamove_order_id)
            if not ok:
                # Lalamove rejected the cancel (e.g. already in flight) — DO NOT mark CANCELLED in DB,
                # otherwise UI lies about a delivery that's still happening.
                raise HTTPException(status_code=409, detail="Lalamove refused to cancel — delivery may already be in progress")

        dao_deliveries.update_delivery(delivery["id"], {"status": "CANCELLED"})

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in DELETE /deliveries/{order_id}/cancel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
