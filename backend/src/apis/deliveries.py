import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from decimal import Decimal
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Request

from core.auth import verify_token
from core.phone import to_e164_vn
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_deliveries import DAODeliveries
from dao.dao_orders import DAOOrders, TRIP_ENDED
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from services.invoice_service import create_invoice_for_done_order
from services import allingo_service, push_service
from services.allingo_service import AllingoError, address, trip_fields
from services.lalamove_service import get_lalamove_service

router = APIRouter(prefix="/deliveries")
logger = logging.getLogger(__name__)


def rebook_max() -> int:
    """How many times a seller may rebook a driver after Lalamove ends a trip (admin_settings)."""
    return DAOAdminConfig().get_positive_int("seller_rebook_max", 3)


def lalamove_recipient(order: dict) -> dict:
    """place_order's recipient for an order read by read_order_with_seller_coords: the receiver saved with
    the order (docs/dev/delivery-recipient R3), else the buyer's profile (orders placed before it).
    The note (house number, floor, gate) goes ahead of the address so the driver reads it first."""
    buyer = order.get("users") or {}
    phone = order.get("receiver_phone")
    try:
        phone = to_e164_vn(phone or buyer.get("phone") or "")
    except ValueError as e:
        if phone:
            raise HTTPException(status_code=400, detail={"code": "receiver_phone_invalid", "message": f"Receiver phone invalid: {e}"})
        raise HTTPException(status_code=400, detail={"code": "buyer_phone_invalid", "message": f"Buyer phone invalid: {e}. Buyer must update phone before delivery."})
    return {
        "recipient_name": order.get("receiver_name") or buyer.get("name") or buyer.get("email") or "Customer",
        "recipient_phone": phone,
        "recipient_remarks": " | ".join(filter(None, (order.get("delivery_note"), order.get("delivery_address")))),
    }


def quote_trip(lalamove, **stops):
    """The fee from the company new trips go to (admin_settings delivery_provider_allingo), as a QuotationResult.
    stops = get_quotation's arguments; lalamove = the caller's get_lalamove_service."""
    if allingo_service.enabled():
        return allingo_service.get_allingo_service().quote(
            address(stops["pickup_address"], stops["pickup_lat"], stops["pickup_lon"]),
            address(stops["dropoff_address"], stops["dropoff_lat"], stops["dropoff_lon"]))
    return lalamove().get_quotation(**stops)


def book_allingo(order: dict, sender_phone: str, recipient: dict, attempts: int) -> tuple[dict, bool]:
    """Book an AllinGo trip for an order read by read_order_with_seller_coords; returns (deliveries columns,
    taken = the trip was booked before this call). Every try first takes a trip still running for this order
    (an earlier try or tap may have made one), so a lost answer never books twice. A failed quote answers 502
    and changes nothing (as with Lalamove); booking retries network / 5xx / 408 / 429 only. Raises AllingoError."""
    service = allingo_service.get_allingo_service()
    seller = order.get("seller_profiles") or {}
    pickup = address(seller.get("address") or "", seller.get("lat"), seller.get("lon"),
                     seller.get("store_name") or "Seller", sender_phone)
    dropoff = address(order.get("delivery_address") or "", order.get("delivery_lat"), order.get("delivery_lon"),
                      recipient["recipient_name"], recipient["recipient_phone"], recipient["recipient_remarks"])
    quote, last_error = None, None
    for attempt in range(1, attempts + 1):
        running = service.find_live_order(order["id"])
        if running:
            logger.warning(f"[Delivery] order={order['id']} takes AllinGo trip {running['id']} booked by an earlier try")
            return trip_fields(running), True
        if quote is None:
            try:
                quote = service.quote(pickup, dropoff)
            except AllingoError as e:
                logger.error(f"[Delivery] AllinGo quote failed for order={order['id']}: {e.code}")
                raise HTTPException(status_code=502, detail="Could not get a delivery fee quote. Please try again.")
        try:
            trip = service.place_order(quote, pickup, dropoff, order["id"])
        except AllingoError as e:
            last_error = e
            logger.warning(f"[Delivery] AllinGo attempt {attempt}/{attempts} failed for order={order['id']}: {e.code}")
            if e.code == allingo_service.WALLET_EMPTY:
                push_service.notify_admins("admin_delivery_wallet_empty", f"/orders?open={order['id']}", code=order["id"][:8])
            if not e.retryable:
                break
            continue
        # A second fence only: a cash trip also answers fee.cod 0 (sandbox 09/11), so this proves nothing
        if Decimal(str((trip.get("fee") or {}).get("cod") or 0)) != 0:
            logger.error(f"[Delivery] AllinGo trip {trip['id']} for order={order['id']} has COD; cancelling it")
            service.cancel_order(trip["id"])
            raise AllingoError("allingo_cod_not_zero")
        return trip_fields(trip), False
    raise last_error


def keep_taken_trip(taken: bool, dao_orders, order_id: str) -> bool:
    """A status write slipped after booking. A trip this call booked is cancelled (as before). A trip taken
    over from an earlier call (a double tap) is that call's: kept unless the order is now cancelled."""
    return taken and (dao_orders.read_order_by_id_raw(order_id) or {}).get("status") != "cancelled"


def cancel_trip(trip: dict, lalamove) -> bool:
    """Cancel a booked trip at the company that booked it (deliveries.provider; NULL rows predate AllinGo
    and are Lalamove). lalamove = the caller's get_lalamove_service."""
    if trip.get("provider") == "allingo":
        return allingo_service.get_allingo_service().cancel_order(trip["allingo_order_id"])
    return lalamove().cancel_order(trip["lalamove_order_id"])


def order_follows_trip(dao_orders, order_id: str, trip_status: str, background_tasks: BackgroundTasks):
    """A webhook's effect on the ORDER, decided by the order's own status, not by whether the trip row just
    changed: a retried event finishes what a failed run began. The push goes with the order change, so once."""
    if trip_status == "COMPLETED":
        order = dao_orders.read_order_by_id_raw(order_id)
        # Not a cancelled (refunded) order: a late COMPLETED must not make it a paid-out done order
        if order and order["status"] in ("ready", "delivery_failed"):
            updated = dao_orders.update_order_status(order_id, "done", expected_status=order["status"])
            if updated:
                push_service.notify_seller_delivered(updated)
                background_tasks.add_task(create_invoice_for_done_order, updated)
    elif trip_status in TRIP_ENDED:
        order = dao_orders.read_order_by_id_raw(order_id)
        if order and order["status"] == "ready":
            if dao_orders.update_order_status(order_id, "delivery_failed"):
                push_service.notify_admins("admin_delivery_failed", f"/orders?open={order['id']}", code=order["id"][:8])
            logger.warning(f"[Webhook] order={order_id} → delivery_failed (trip={trip_status})")


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

        result = quote_trip(
            get_lalamove_service,
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
async def delivery_webhook(request: Request, background_tasks: BackgroundTasks):
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

        # Lalamove's URL verification (on webhook registration) has no apiKey/signature and must get a 200.
        if not api_key and not signature:
            return {"success": True}

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
        # A row rebooked to AllinGo: a late Lalamove event is about the old trip, not this one
        if not delivery or delivery.get("provider") == "allingo":
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
        # Order list badges show the delivery status: move the seller's list signature too
        dao_orders.touch_order(delivery["order_id"])

        if event_type == "DRIVER_ASSIGNED":
            order = dao_orders.read_order_by_id_raw(delivery["order_id"])
            if order:
                push_service.notify_seller_driver_assigned(order)

        order_follows_trip(dao_orders, delivery["order_id"], new_status, background_tasks)

        return {"success": True}

    except HTTPException:
        # Auth/signature failures — propagate proper status to Lalamove
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /deliveries/webhook: {e}")
        # Still return 200 to avoid Lalamove retry storms on our own bugs
        return {"success": False, "detail": "Internal error"}


# Trip progress for out-of-order AllinGo events: a status is written only when it ranks higher. Every ended
# status ranks top, including Lalamove's and the CANCELLED our own cancel writes, so nothing moves after an end.
TRIP_RANK = {"ASSIGNING_DRIVER": 1, "ON_GOING": 2, "PICKED_UP": 3}


def trip_rank(status) -> int:
    return 4 if status == "COMPLETED" or status in TRIP_ENDED else TRIP_RANK.get(status, 0)


def allingo_signature_ok(secret: str, header: str, raw_body: bytes) -> bool:
    """X-AllinGo-Signature "t=<seconds>,v1=<hex>": v1 = HMAC-SHA256(secret, "<t>.<raw body>"), t within 300 s."""
    parts = dict(p.strip().split("=", 1) for p in header.split(",") if "=" in p)
    try:
        fresh = abs(time.time() - int(parts.get("t", ""))) <= 300
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), parts["t"].encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return fresh and hmac.compare_digest(expected.encode(), parts.get("v1", "").encode())


def booking_in_flight(dao_orders, dao_deliveries, order_id) -> bool:
    """Ready books the trip first and inserts the deliveries row after, so an event can arrive in between:
    the order (external_reference) is still confirmed and has no trip row yet."""
    try:
        uuid.UUID(str(order_id))
    except ValueError:
        return False
    order = dao_orders.read_order_by_id_raw(order_id)
    return bool(order and order["status"] == "confirmed" and not dao_deliveries.read_delivery_by_order_id(order_id))


# --------------------------------------------------------------------------
# POST /deliveries/webhook/allingo — AllinGo trip events (public)
# Errors answer 5xx on purpose (unlike Lalamove's 200): AllinGo resends up to 8 times over 44 hours.
# --------------------------------------------------------------------------
@router.post("/webhook/allingo")
async def allingo_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    secret = os.getenv("ALLINGO_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("AllinGo webhook: ALLINGO_WEBHOOK_SECRET not configured — rejecting")
        raise HTTPException(status_code=503, detail="Webhook not configured")
    if not allingo_signature_ok(secret, request.headers.get("X-AllinGo-Signature", ""), raw_body):
        logger.warning("AllinGo webhook: bad or stale signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = json.loads(raw_body)
        data = event.get("data") or {}
        trip = data.get("object") or {}
        dao_deliveries, dao_orders = DAODeliveries(), DAOOrders()
        delivery = dao_deliveries.read_delivery_by_allingo_order_id(trip["id"]) if trip.get("id") else None
        if not delivery or delivery.get("provider") != "allingo":
            if booking_in_flight(dao_orders, dao_deliveries, trip.get("external_reference")):
                raise HTTPException(status_code=503, detail="Delivery not recorded yet")
            logger.warning(f"AllinGo webhook: no delivery row for {trip.get('id')} ({event.get('type')})")
            return {"success": True}

        leg = trip.get("delivery") or {}
        current = delivery.get("status")
        new = allingo_service.STATUS.get(leg.get("status"))
        update = {"status": new} if new and trip_rank(new) > trip_rank(current) else {}
        status = update.get("status", current)

        driver_changed = False
        if update.get("status") in TRIP_ENDED:
            # Like Lalamove's failed end: no driver or tracking link left on screen
            update |= dict.fromkeys(("driver_name", "driver_phone", "driver_plate", "share_link"))
        elif trip_rank(status) < 4:
            driver = leg.get("driver") or data.get("driver") or {}
            seen = (driver.get("phone"), driver.get("license_plate"))
            # A new driver, also a replacement; the same one sent again is no news
            if any(seen) and seen != (delivery.get("driver_phone"), delivery.get("driver_plate")):
                update |= {"driver_name": driver.get("name"), "driver_phone": seen[0], "driver_plate": seen[1]}
                driver_changed = True
            if leg.get("track_link") and leg["track_link"] != delivery.get("share_link"):
                update["share_link"] = leg["track_link"]

        if update:
            dao_deliveries.update_delivery(delivery["id"], update)
        logger.warning(f"[Webhook] AllinGo {event.get('type')} → trip={trip['id']} {leg.get('status')} → {status}")
        dao_orders.touch_order(delivery["order_id"])
        if driver_changed:
            order = dao_orders.read_order_by_id_raw(delivery["order_id"])
            if order:
                push_service.notify_seller_driver_assigned(order)
        order_follows_trip(dao_orders, delivery["order_id"], status, background_tasks)
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /deliveries/webhook/allingo: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


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
                "rebook_max": rebook_max(),
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
        if order.get("payment_status") != "paid":   # never book a real trip for an unpaid order
            raise HTTPException(status_code=409, detail={"code": "order_not_paid", "message": "This order is not paid yet."})

        dao_deliveries = DAODeliveries()
        delivery = dao_deliveries.read_delivery_by_order_id(order_id)
        if not delivery or delivery["status"] not in ("CANCELLED", "CANCELED", "REJECTED", "EXPIRED"):
            raise HTTPException(status_code=400, detail="No cancelled delivery to rebook")

        rebook_count = delivery.get("rebook_count", 0)
        if rebook_count >= rebook_max():
            raise HTTPException(status_code=400, detail="Max rebook attempts reached")

        full_order = dao_orders.read_order_with_seller_coords(order_id)
        if not full_order:
            raise HTTPException(status_code=500, detail="Could not load order details")

        seller  = full_order.get("seller_profiles") or {}

        try:
            sender_phone = to_e164_vn(seller.get("phone") or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail={"code": "seller_phone_invalid", "message": f"Seller phone invalid: {e}"})
        recipient = lalamove_recipient(full_order)

        if allingo_service.enabled():
            try:
                trip, taken = book_allingo(full_order, sender_phone, recipient, attempts=1)
            except AllingoError:
                # The order stays delivery_failed (no cancel, no refund): the seller rebooks once the wallet is topped up
                raise HTTPException(status_code=503, detail="Unable to book a delivery driver. Please try again later.")
        else:
            service = get_lalamove_service()
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
                **recipient,
            )
            trip = {"provider": "lalamove", "status": result.status, "lalamove_order_id": result.lalamove_order_id,
                    "allingo_order_id": None, "share_link": result.share_link or ""}
            taken = False
        trip_id = trip["allingo_order_id"] or trip["lalamove_order_id"]

        try:
            dao_deliveries.update_delivery(delivery["id"], {
                **trip,
                "driver_name": None,
                "driver_phone": None,
                "driver_plate": None,
                "rebook_count": rebook_count + 1,
            })
        except Exception as db_err:
            # DB write failed but the trip is already booked — roll back to avoid orphan order.
            logger.error(f"[Delivery] DB update failed after rebook ({trip['provider']}={trip_id}); cancelling the trip")
            try:
                cancel_trip(trip, get_lalamove_service)
            except Exception as cancel_err:
                logger.error(f"[Delivery] Rollback cancel also failed for {trip_id}: {cancel_err}")
            raise HTTPException(status_code=500, detail=f"Rebook DB update failed: {db_err}")

        # Conditional: the buyer may have cancelled the late order meanwhile (R6) → drop the new trip
        if order["status"] == "delivery_failed" and not dao_orders.update_order_status(order_id, "ready", expected_status="delivery_failed"):
            if not keep_taken_trip(taken, dao_orders, order_id) and not cancel_trip(trip, get_lalamove_service):
                logger.error(f"[Delivery] order={order_id} changed while rebooking; cancel of {trip['provider']}={trip_id} failed — MANUAL INTERVENTION NEEDED")
            raise HTTPException(status_code=409, detail="Order status changed, please refresh")

        logger.warning(f"[Delivery] Re-booked order={order_id} attempt={rebook_count + 1} {trip['provider']}={trip_id}")

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

        trip_id = delivery.get("allingo_order_id" if delivery.get("provider") == "allingo" else "lalamove_order_id")
        if trip_id and not cancel_trip(delivery, get_lalamove_service):
            # The company rejected the cancel (e.g. already in flight) — DO NOT mark CANCELLED in DB,
            # otherwise UI lies about a delivery that's still happening.
            raise HTTPException(status_code=409, detail="Lalamove refused to cancel — delivery may already be in progress")

        dao_deliveries.update_delivery(delivery["id"], {"status": "CANCELLED"})

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in DELETE /deliveries/{order_id}/cancel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
