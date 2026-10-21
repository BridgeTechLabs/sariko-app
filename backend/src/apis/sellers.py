import logging
import re

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from apis.orders import cancel_after
from core.store_hours import VN_TZ, confirm_deadline, is_open_now
from services.order_expiry import confirm_window

from dao.dao_admin_config import DAOAdminConfig
from dao.dao_admin_payouts import DAOAdminPayouts
from dao.dao_seller_profiles import DAOSellerProfiles
from dao.dao_food_items import DAOFoodItems, FoodItemNameTaken
from dao.dao_menu_categories import DAOMenuCategories
from dao.dao_reviews import DAOReviews

from fastapi import APIRouter, HTTPException, Depends, Query, status

from apis.reviews import mask_reviewer
from core.auth import verify_token
from core.phone import to_e164_vn
from core.sariko_cache import cache
from dao.dao_orders import DAOOrders, seller_orders_key
from schemas import Schema
from dao.dao_food_item_variants import DAOFoodItemVariants
from utils.storage import upload_image_base64

router = APIRouter(prefix="/sellers")
logger = logging.getLogger(__name__)


VALID_STATUS_TRANSITIONS = {
    "pending":          ["confirmed", "cancelled"],
    "confirmed":        ["ready", "cancelled"],
    # No seller cancel once a Lalamove driver is booked: the API only cancels before
    # or within 5 min of matching, so Sariko cancels the trip and the order (T75).
    # delivery_failed is set by webhook only; its trip has already ended.
    "ready":            ["done"],
    "delivery_failed":  ["done", "cancelled"],
}

# A Lalamove trip is over once it reaches one of these; before that the COMPLETED
# webhook closes the order, so the seller can't mark it done (P0-6).
DELIVERY_ENDED_STATUSES = {"COMPLETED", "REJECTED", "CANCELLED", "CANCELED", "EXPIRED"}

# Rows one order search returns (a page size, not a business rule).
SEARCH_LIMIT = 20
# Payout batches shown on the earnings page (a page size, not a business rule).
EARNINGS_PAYOUTS_LIMIT = 12

@router.get("/")
def get_sellers(user=Depends(verify_token)):
    pass


@router.get("/founding")
def get_founding_sellers():

    dao_seller_profiles = DAOSellerProfiles()
    sellers = dao_seller_profiles.read_founding_sellers()

    return {"success": True, "founding_sellers": sellers}


@router.get("/founding/slots")
def get_founding_slots():
    """Founding places left, for the "become a seller" card. Every seller on the
    founding tier takes one, whether listed yet or not. Total = admin_settings.founding_slots."""
    total = DAOAdminConfig().get_positive_int("founding_slots", 50)
    taken = DAOSellerProfiles().count_sellers_by_tier("founding")
    return {"success": True, "slots_left": max(0, total - taken)}


# ── Seller Dashboard Endpoints (must be before /{slug_name} wildcard) ──

def _get_seller(user):
    profile = DAOSellerProfiles().read_seller_profile_by_user_id(user["id"])
    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
    return profile


def _get_seller_id(user):
    return _get_seller(user)["id"]


def _with_deadlines(orders: list, seller: dict) -> list:
    """`deadline` shown under the seller's Accept / Ready buttons.
    pending (paid): when it auto-cancels; None while the store is closed, that clock is paused.
    confirmed: when the buyer may cancel it for a full refund (R4)."""
    now = datetime.now(timezone.utc)
    opening, closing = seller.get("opening_time"), seller.get("closing_time")
    window = None
    for order in orders:
        order["deadline"] = None
        if (order["status"] == "pending" and order.get("payment_status") == "paid" and order.get("paid_at")
                and is_open_now(seller.get("is_open"), opening, closing, now)):
            window = window or confirm_window()
            opened_at = seller.get("opened_at")
            order["deadline"] = confirm_deadline(datetime.fromisoformat(order["paid_at"]), opening, closing,
                                                 datetime.fromisoformat(opened_at) if opened_at else None,
                                                 now, window).isoformat()
        elif order["status"] == "confirmed" and order.get("status_changed_at"):
            order["deadline"] = cancel_after(order).isoformat()
    return orders


@router.get("/me")
def get_seller_info(user=Depends(verify_token)):
    try:
        dao = DAOSellerProfiles()
        profile = dao.read_seller_profile_by_user_id(user["id"])
        if not profile:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
        return {
            "success": True,
            "seller_id": profile["id"],
            "slug": profile.get("slug"),
            "store_name": profile.get("store_name"),
            "address": profile.get("address"),
            "lat": profile.get("lat"),
            "lon": profile.get("lon"),
            "phone": profile.get("phone"),
            "has_address": bool(profile.get("address") and profile.get("lat") and profile.get("lon")),
            "has_phone": bool(profile.get("phone")),
            "is_open": profile.get("is_open") is not False,   # the switch itself
            "opening_time": profile.get("opening_time"),
            "closing_time": profile.get("closing_time"),
            "open_now": is_open_now(profile.get("is_open"), profile.get("opening_time"), profile.get("closing_time")),
            "rating_avg": profile.get("rating_avg"),
            "rating_count": profile.get("rating_count") or 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))\
        

@router.patch("/me/open")
def set_store_open(body: Schema.RequestSetStoreOpen, user=Depends(verify_token)):
    """Open/close the store. Closing only stops new same-day orders; existing orders still
    need handling, and pre-orders stay possible (see apis/orders.py STORE_CLOSED_DETAIL)."""
    try:
        updated = DAOSellerProfiles().update_seller_profile_info(user["id"], {"is_open": body.is_open})
        if not updated:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
        return {
            "success": True,
            "is_open": updated["is_open"],
            "open_now": is_open_now(updated["is_open"], updated.get("opening_time"), updated.get("closing_time")),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/open: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/hours")
def set_store_hours(body: Schema.RequestSetStoreHours, user=Depends(verify_token)):
    """Daily opening hours (same every day); both null = all day. The open switch still wins."""
    try:
        fields = {
            "opening_time": body.opening_time.isoformat() if body.opening_time else None,
            "closing_time": body.closing_time.isoformat() if body.closing_time else None,
        }
        updated = DAOSellerProfiles().update_seller_profile_info(user["id"], fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
        return {
            "success": True,
            "opening_time": updated["opening_time"],
            "closing_time": updated["closing_time"],
            "open_now": is_open_now(updated["is_open"], updated["opening_time"], updated["closing_time"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/hours: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/orders")
def get_seller_orders(user=Depends(verify_token)):
    try:
        seller = _get_seller(user)
        history_days = DAOAdminConfig().get_positive_int("seller_order_history_days", 30)
        since = datetime.now(timezone.utc) - timedelta(days=history_days)
        orders = DAOOrders().read_orders_by_seller_id(seller["id"], since)
        return {"success": True, "orders": _with_deadlines(orders, seller), "seller_id": seller["id"],
                "history_days": history_days}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Must stay above /me/orders/{order_id} — FastAPI matches routes in declaration
# order, otherwise "head" is read as an order id.
@router.get("/me/orders/head")
def get_seller_orders_head(user=Depends(verify_token)):
    """Polling probe: newest updated_at + row count for the seller's paid orders.

    The dashboard compares this signature against the previous one and only
    fetches the full (joined) list when it moves. Served from the shared cache,
    so a tick that finds nothing changed costs no query against orders at all —
    dao_orders invalidates the key on every write.
    """
    try:
        seller_id = _get_seller_id(user)
        key = seller_orders_key(seller_id)

        signature = cache.get(key)
        cached = signature is not None
        if not cached:
            signature = DAOOrders().read_orders_head_by_seller_id(seller_id)
            cache.put(key, signature)

        return {"success": True, "cached": cached, **signature}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders/head: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Must stay above /me/orders/{order_id}, like /head.
@router.get("/me/orders/search")
def search_seller_orders(user=Depends(verify_token), q: str = Query(min_length=2, max_length=60)):
    """Find an order of any age by its code (#54CB066E, or the start of it) or the buyer's name."""
    try:
        seller = _get_seller(user)
        term = q.strip().lstrip("#").strip()
        code = term.lower() if re.fullmatch(r"[0-9a-fA-F-]{2,36}", term) else None
        if code:
            code = code.replace("-", "")
        # Keep letters, digits, spaces and . ' - : anything else could act as a PostgREST
        # filter or LIKE character.
        name = re.sub(r"[^\w\s.'-]|_", "", term).strip() or None
        orders = DAOOrders().search_orders_for_seller(seller["id"], code, name, limit=SEARCH_LIMIT)
        return {"success": True, "orders": _with_deadlines(orders, seller)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders/search: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/orders/{order_id}")
def get_seller_order_detail(order_id: str, user=Depends(verify_token)):
    try:
        seller = _get_seller(user)
        dao = DAOOrders()
        order = dao.read_order_by_id_for_seller(order_id, seller["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        order["status_history"] = dao.read_status_history(order_id)
        return {"success": True, "order": _with_deadlines([order], seller)[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders/{order_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/orders/{order_id}/status")
def update_seller_order_status(order_id: str, body: Schema.RequestUpdateOrderStatus, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        dao_orders = DAOOrders()

        order = dao_orders.read_order_by_id_for_seller(order_id, seller_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        allowed = VALID_STATUS_TRANSITIONS.get(order["status"], [])
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{order['status']}' to '{body.status}'"
            )

        if order["status"] == "ready" and body.status == "done" and order.get("delivery_method") == "delivery":
            from dao.dao_deliveries import DAODeliveries
            delivery = DAODeliveries().read_delivery_by_order_id(order_id)
            if delivery and delivery.get("status") not in DELIVERY_ENDED_STATUSES:
                raise HTTPException(status_code=409, detail={
                    "code": "delivery_in_progress",
                    "message": "The rider is still delivering; the order completes itself when the delivery is done.",
                })

        # Pass cancellation_reason when rejecting
        cancellation_reason = body.cancellation_reason if body.status == "cancelled" else None

        # For "ready" + delivery: book Lalamove FIRST, only update status if booking succeeds
        booking_result = None
        if body.status == "ready" and order.get("delivery_method") == "delivery":
            from services.lalamove_service import get_lalamove_service
            from dao.dao_deliveries import DAODeliveries

            full_order = dao_orders.read_order_with_seller_coords(order_id)
            if not full_order:
                raise HTTPException(status_code=500, detail="Could not load order details for delivery")

            seller  = full_order.get("seller_profiles") or {}
            buyer   = full_order.get("users") or {}

            # Same check as the Ready buttons (P1-4): no pickup point or phone, no quote.
            missing = [field for field, ok in (
                ("address", seller.get("address") and seller.get("lat") and seller.get("lon")),  # as has_address
                ("phone", seller.get("phone")),
            ) if not ok]
            if missing:
                raise HTTPException(status_code=409, detail={
                    "code": "seller_profile_incomplete",
                    "missing": missing,
                    "message": "Set your store address and phone before marking the order ready.",
                })

            pickup_address  = seller.get("address") or ""
            dropoff_address = full_order.get("delivery_address") or ""

            if not pickup_address.strip() or not dropoff_address.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Missing pickup or dropoff address. Please update your store address in settings."
                )

            service = get_lalamove_service()

            # Re-quote (original quotation has expired)
            quotation = service.get_quotation(
                pickup_lat=float(seller.get("lat") or 0),
                pickup_lon=float(seller.get("lon") or 0),
                pickup_address=pickup_address,
                dropoff_lat=float(full_order.get("delivery_lat") or 0),
                dropoff_lon=float(full_order.get("delivery_lon") or 0),
                dropoff_address=dropoff_address,
            )

            try:
                sender_phone = to_e164_vn(seller.get("phone") or "")
            except ValueError as e:
                raise HTTPException(status_code=400, detail={"code": "seller_phone_invalid", "message": f"Seller phone invalid: {e}. Update store phone in settings."})
            try:
                recipient_phone = to_e164_vn(buyer.get("phone") or "")
            except ValueError as e:
                raise HTTPException(status_code=400, detail={"code": "buyer_phone_invalid", "message": f"Buyer phone invalid: {e}. Buyer must update phone before delivery."})

            logger.warning(f"[Delivery] order={order_id} sender_phone={sender_phone} recipient_phone={recipient_phone}")

            booking_result = None
            last_booking_error = None
            attempts = DAOAdminConfig().get_positive_int("driver_booking_attempts", 3)
            for attempt in range(1, attempts + 1):
                try:
                    booking_result = service.place_order(
                        quotation_id=quotation.quotation_id,
                        stop_id_0=quotation.stop_id_0,
                        stop_id_1=quotation.stop_id_1,
                        sender_name=seller.get("store_name", "Seller"),
                        sender_phone=sender_phone,
                        recipient_name=buyer.get("name") or buyer.get("email") or "Customer",
                        recipient_phone=recipient_phone,
                        recipient_remarks=full_order.get("delivery_address") or "",
                    )
                    break
                except Exception as e:
                    last_booking_error = e
                    logger.warning(f"[Delivery] place_order attempt {attempt}/{attempts} failed for order={order_id}: {e}")

            if booking_result is None:
                logger.error(f"[Delivery] All {attempts} booking attempts failed for order={order_id}: {last_booking_error}")
                # The buyer UI translates this exact text (OrderStatusHeader.vue); no count in it, it's a setting
                dao_orders.update_order_status(order_id, "cancelled", "Driver booking failed")
                from dao.dao_refunds import DAORefunds
                DAORefunds().create_refund_for_order(order, "driver_booking_failed")
                raise HTTPException(status_code=503, detail="Unable to book a delivery driver. Your order has been cancelled.")

            dao_deliveries = DAODeliveries()
            try:
                dao_deliveries.create_delivery(
                    order_id=order_id,
                    provider="lalamove",
                    status=booking_result.status,
                    user_id=full_order.get("user_id"),
                    seller_user_id=full_order.get("seller_user_id"),
                    lalamove_order_id=booking_result.lalamove_order_id,
                    share_link=booking_result.share_link,
                )
            except Exception as db_err:
                # DB insert failed but Lalamove already booked a driver — roll back to avoid orphan.
                logger.error(f"[Delivery] create_delivery failed (lalamove={booking_result.lalamove_order_id}); cancelling Lalamove order")
                try:
                    service.cancel_order(booking_result.lalamove_order_id)
                except Exception as cancel_err:
                    logger.error(f"[Delivery] Rollback cancel failed for {booking_result.lalamove_order_id}: {cancel_err} — MANUAL INTERVENTION NEEDED")
                raise HTTPException(status_code=500, detail=f"Failed to record delivery: {db_err}")
            logger.warning(f"[Delivery] Auto-booked order={order_id} lalamove={booking_result.lalamove_order_id}")

        # Only update status after delivery booking succeeds (or if not a delivery order).
        # Conditional on the status read above: the confirm-timeout job or a buyer
        # cancelling a late order may have cancelled (and refunded) it in between.
        updated = dao_orders.update_order_status(order_id, body.status, cancellation_reason,
                                                 expected_status=order["status"])
        if not updated:
            # The trip was booked for an order that is no longer ours to send (R4.6).
            # It is still ASSIGNING_DRIVER, which Lalamove lets us cancel.
            if booking_result and not service.cancel_order(booking_result.lalamove_order_id):
                logger.error(f"[Delivery] order={order_id} changed while booking; cancel of lalamove={booking_result.lalamove_order_id} failed — MANUAL INTERVENTION NEEDED")
            raise HTTPException(status_code=409, detail="Order status changed, please refresh")

        if body.status == "cancelled":
            from dao.dao_refunds import DAORefunds
            DAORefunds().create_refund_for_order(order, "seller_cancel")

        return {"success": True, "order": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/orders/{order_id}/status: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))



def _make_price_text(price: int) -> str:
    formatted = "{:,.0f}".format(price).replace(",", ".")
    return f"{formatted} ₫"


# ── Seller Menu Endpoints ──────────────────────────────────────────────────────

@router.get("/me/menu")
def get_seller_menu(user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        return {"success": True, "menu": DAOFoodItems().read_menu_by_seller_id(seller_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/menu: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me/menu/categories")
def create_category(body: Schema.RequestCreateCategory, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        cat = DAOMenuCategories().create(seller_id, body.name, body.sort_order or 0)
        return {"success": True, "category": cat}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /sellers/me/menu/categories: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/menu/categories/{cat_id}")
def update_category(cat_id: str, body: Schema.RequestUpdateCategory, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        fields = body.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        cat = DAOMenuCategories().update(cat_id, seller_id, fields)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        return {"success": True, "category": cat}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/menu/categories/{cat_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/me/menu/categories/{cat_id}")
def delete_category(cat_id: str, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        DAOMenuCategories().delete(cat_id, seller_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in DELETE /sellers/me/menu/categories/{cat_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me/menu/items")
def create_food_item(body: Schema.RequestCreateFoodItem, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        fields = body.model_dump(exclude_none=True)
        fields["price_text"] = _make_price_text(body.price)
        item = DAOFoodItems().create(seller_id, fields)
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except FoodItemNameTaken:
        raise HTTPException(status_code=409, detail="You already have a dish with this name in this category")
    except Exception as e:
        logger.exception(f"Exception in POST /sellers/me/menu/items: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/menu/items/{item_id}")
def update_food_item(item_id: str, body: Schema.RequestUpdateFoodItem, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        fields = body.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        if "price" in fields:
            fields["price_text"] = _make_price_text(fields["price"])
        item = DAOFoodItems().update(item_id, seller_id, fields)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except FoodItemNameTaken:
        raise HTTPException(status_code=409, detail="You already have a dish with this name in this category")
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/menu/items/{item_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _assert_owns_variant(variant_id: str, seller_id: str):
    """A variant carries no seller_id, so ownership is checked one hop up through
    the dish it belongs to. Without this any seller could edit another's prices."""
    item_id = DAOFoodItemVariants().read_parent_item_id(variant_id)
    if not item_id or not DAOFoodItems().read_owned_by_seller(item_id, seller_id):
        raise HTTPException(status_code=404, detail="Variant not found")


@router.post("/me/menu/items/{item_id}/variants")
def create_variant(item_id: str, body: Schema.RequestCreateVariant, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        if not DAOFoodItems().read_owned_by_seller(item_id, seller_id):
            raise HTTPException(status_code=404, detail="Item not found")
        fields = body.model_dump(exclude_none=True)
        fields["price_text"] = _make_price_text(body.price)
        variant = DAOFoodItemVariants().create(item_id, fields)
        return {"success": True, "variant": variant}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /sellers/me/menu/items/{item_id}/variants: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/menu/variants/{variant_id}")
def update_variant(variant_id: str, body: Schema.RequestUpdateVariant, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        _assert_owns_variant(variant_id, seller_id)
        fields = body.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        if "price" in fields:
            fields["price_text"] = _make_price_text(fields["price"])
        variant = DAOFoodItemVariants().update(variant_id, fields)
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        return {"success": True, "variant": variant}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/menu/variants/{variant_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/me/menu/variants/{variant_id}")
def delete_variant(variant_id: str, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        _assert_owns_variant(variant_id, seller_id)
        DAOFoodItemVariants().delete(variant_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in DELETE /sellers/me/menu/variants/{variant_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me/menu/items/{item_id}/image")
def upload_food_item_image(item_id: str, body: Schema.RequestUploadImage, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        # New path per upload: the previous photo stays in storage for history_menu (T31)
        path = f"food-items/{seller_id}/{item_id}-{int(datetime.now(timezone.utc).timestamp())}"
        image_url = upload_image_base64(path, body.image_base64)
        return {"success": True, "image_url": image_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in POST /sellers/me/menu/items/{item_id}/image: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/me/menu/items/{item_id}")
def delete_food_item(item_id: str, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        DAOFoodItems().delete(item_id, seller_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in DELETE /sellers/me/menu/items/{item_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/reviews")
def get_seller_reviews(
    user=Depends(verify_token),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    try:
        seller_id = _get_seller_id(user)
        reviews = DAOReviews().read_reviews_by_seller_id(
            seller_id=seller_id, limit=limit, offset=offset
        )
        for review in reviews:
            mask_reviewer(review)

        return {"success": True, "reviews": reviews}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/reviews: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def _vnd(amount: Decimal) -> int:
    """Whole đồng for the JSON, rounded half up like the admin screens (DB keeps 2 decimals)."""
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@router.get("/me/earnings")
def get_seller_earnings(user=Depends(verify_token)):
    """Done orders of the last seller_order_history_days with their split (food, commission,
    VAT, payout) and payout state, plus the seller's payout batches. Sums in Decimal,
    int only in the JSON."""
    try:
        seller_id = _get_seller_id(user)
        config = DAOAdminConfig()
        history_days = config.get_positive_int("seller_order_history_days", 30)
        delay_days = config.get_int_in_range("payout_delay_days", 3, 0, 30)
        since = datetime.now(timezone.utc) - timedelta(days=history_days)

        orders, awaiting = [], Decimal(0)
        for row in DAOOrders().read_done_orders_for_earnings(seller_id, since):
            # What reaches the seller: the order's payout minus the tax withheld from it
            payout = _money(row.get("payout_amount"))
            withheld = _money(row.get("wh_vat_amount")) + _money(row.get("wh_pit_amount"))
            state = row.get("payout_status") or "pending"
            if state == "pending" and row.get("payout_hold"):
                state = "held"
            expected = None
            if state == "pending":
                awaiting += payout - withheld
                done_day = datetime.fromisoformat(row["status_changed_at"]).astimezone(VN_TZ).date()
                expected = (done_day + timedelta(days=delay_days)).isoformat()
            elif state == "processing":
                awaiting += payout - withheld
            orders.append({
                "id": row["id"],
                "done_at": row.get("status_changed_at"),
                "subtotal": _vnd(_money(row.get("subtotal"))),
                "commission_amount": _vnd(_money(row.get("commission_amount"))),
                "vat_amount": _vnd(_money(row.get("vat_amount"))),
                "payout_amount": _vnd(payout),
                "wh_vat_amount": _vnd(_money(row.get("wh_vat_amount"))),   # 0 until computed
                "wh_pit_amount": _vnd(_money(row.get("wh_pit_amount"))),
                "payout_state": state,
                "expected_payout_date": expected,
            })

        payouts, received = [], Decimal(0)
        for row in DAOAdminPayouts().read_payouts_by_seller_id(seller_id, EARNINGS_PAYOUTS_LIMIT):
            net = _money(row.get("net_payout"))
            if row.get("status") == "completed":
                received += net
            payouts.append({
                **row,
                "net_payout": _vnd(net),
                "withholding_amount": _vnd(_money(row.get("withholding_amount"))),
                "total_deductions": _vnd(_money(row.get("total_deductions"))),
            })

        return {
            "success": True,
            "history_days": history_days,
            "payout_delay_days": delay_days,
            "awaiting_total": _vnd(awaiting),
            "received_total": _vnd(received),
            "payouts_limit": EARNINGS_PAYOUTS_LIMIT,   # received_total covers only these batches
            "orders": orders,
            "payouts": payouts,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/earnings: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/featured-dishes")
def get_featured_dishes():
    try:
        dao = DAOFoodItems()
        dishes = dao.read_featured_dishes()
        return {"success": True, "featured_dishes": dishes}
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/featured-dishes: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{slug_name}")
def get_seller_by_slug_name(slug_name):

    dao_seller_profiles = DAOSellerProfiles()
    seller = dao_seller_profiles.read_seller_by_slug_name(slug=slug_name)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    seller["is_founding"] = seller.get("tier") == "founding"
    return {"success": True, "seller": seller}


@router.get("/{slug_name}/menu")
def get_seller_menu_food_items(slug_name: str):

    dao_seller_profiles = DAOSellerProfiles()
    seller = dao_seller_profiles.read_seller_by_slug_name(slug=slug_name)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    dao_food_items = DAOFoodItems()
    food_items = dao_food_items.read_menu_by_seller_id(seller_id=seller["id"])

    return {"success": True, "menus": food_items or []}