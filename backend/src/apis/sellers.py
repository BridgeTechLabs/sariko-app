import functools
import logging
import re
import uuid

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from apis.complaints import complaints_for_order
from apis.deliveries import book_allingo, cancel_trip, check_trip_addresses, keep_taken_trip, lalamove_recipient, seller_phone
from apis.orders import cancel_after
from core.store_hours import confirm_deadline, is_open_now
from services.order_expiry import confirm_window

from dao.dao_admin_config import DAOAdminConfig
from dao.dao_admin_payouts import DAOAdminPayouts
from dao.dao_seller_profiles import DAOSellerProfiles
from dao.dao_food_items import DAOFoodItems, FoodItemNameTaken
from dao.dao_menu_categories import DAOMenuCategories
from dao.dao_menu_option_groups import DAOMenuOptionGroups, OptionNameTaken
from dao.dao_reviews import DAOReviews

from fastapi import APIRouter, HTTPException, Depends, Query, status

from apis.reviews import mask_reviewer
from core.auth import verify_token
from core.payout_cycle import expected_payout_date
from core.sariko_cache import cache
from dao.dao_orders import DAOOrders, TRIP_ENDED, seller_orders_key
from schemas import Schema
from services import allingo_service
from services.allingo_service import AllingoError
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

# What a seller may give as the cancel reason (T178): codes, translated per viewer; "other" carries the seller's
# own words in cancellation_note. NO_DRIVER_REASON is also the automatic cancel after every booking attempt failed.
NO_DRIVER_REASON = "no_driver"
OTHER_REASON = "seller_reject_other"
SELLER_CANCEL_REASONS = {"seller_reject_out_of_ingredients", "seller_reject_too_busy", "seller_reject_store_closing",
                         OTHER_REASON, NO_DRIVER_REASON}

# A Lalamove trip is over once it reaches one of these; before that the COMPLETED
# webhook closes the order, so the seller can't mark it done (P0-6).
DELIVERY_ENDED_STATUSES = TRIP_ENDED | {"COMPLETED"}

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
    confirmed / delivery_failed: when the buyer may cancel it for a full refund (R4, R6)."""
    now = datetime.now(timezone.utc)
    hours = seller.get("weekly_hours")
    window = None
    get_minutes = functools.cache(DAOAdminConfig().get_minutes)   # each setting read once for the whole list
    for order in orders:
        order["deadline"] = None
        if (order["status"] == "pending" and order.get("payment_status") == "paid" and order.get("paid_at")
                and is_open_now(seller.get("is_open"), hours, now, seller.get("id"))):
            window = window or confirm_window()
            opened_at = seller.get("opened_at")
            order["deadline"] = confirm_deadline(datetime.fromisoformat(order["paid_at"]), hours,
                                                 datetime.fromisoformat(opened_at) if opened_at else None,
                                                 now, window, seller.get("id")).isoformat()
        elif order["status"] in ("confirmed", "delivery_failed") and order.get("status_changed_at"):
            order["deadline"] = cancel_after(order, get_minutes).isoformat()
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
            "description": profile.get("description"),
            "address": profile.get("address"),
            "lat": profile.get("lat"),
            "lon": profile.get("lon"),
            "phone": profile.get("phone"),
            "has_address": bool(profile.get("address") and profile.get("lat") and profile.get("lon")),
            "has_phone": bool(profile.get("phone")),
            "is_open": profile.get("is_open") is not False,   # the switch itself
            "weekly_hours": profile.get("weekly_hours"),
            "open_now": is_open_now(profile.get("is_open"), profile.get("weekly_hours"), seller_id=profile["id"]),
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
            "open_now": is_open_now(updated["is_open"], updated.get("weekly_hours"), seller_id=updated.get("id")),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/open: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/hours")
def set_store_hours(body: Schema.RequestSetStoreHours, user=Depends(verify_token)):
    """Weekly opening hours, one slot per day (or a day off); null = all day. The open switch still wins."""
    try:
        updated = DAOSellerProfiles().update_seller_profile_info(user["id"], {"weekly_hours": body.as_json()})
        if not updated:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
        return {
            "success": True,
            "weekly_hours": updated["weekly_hours"],
            "open_now": is_open_now(updated["is_open"], updated["weekly_hours"], seller_id=updated.get("id")),
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
        if order.get("cancellation_reason") != OTHER_REASON:   # the seller gets only its own words, not an admin's (T178)
            order.pop("cancellation_note", None)
        order["status_history"] = dao.read_status_history(order_id)
        order["delivery_history"] = dao.read_delivery_history(order_id)   # BUGS #39: times of the delivery steps
        order |= complaints_for_order(order, user["id"], "seller")   # T35
        return {"success": True, "order": _with_deadlines([order], seller)[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders/{order_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/me/orders/{order_id}/status")
def update_seller_order_status(order_id: str, body: Schema.RequestUpdateOrderStatus, user=Depends(verify_token)):
    until = allingo_service.deadline()   # AllinGo retries stop in time for the seller's answer (T191)
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

        # Only a paid order moves forward: an unpaid one marked ready would book a real Lalamove trip.
        if body.status != "cancelled" and order.get("payment_status") != "paid":
            raise HTTPException(status_code=409, detail={
                "code": "order_not_paid",
                "message": "This order is not paid yet.",
            })

        if order["status"] == "ready" and body.status == "done" and order.get("delivery_method") == "delivery":
            from dao.dao_deliveries import DAODeliveries
            delivery = DAODeliveries().read_delivery_by_order_id(order_id)
            if delivery and delivery.get("status") not in DELIVERY_ENDED_STATUSES:
                raise HTTPException(status_code=409, detail={
                    "code": "delivery_in_progress",
                    "message": "The rider is still delivering; the order completes itself when the delivery is done.",
                })

        # Rejecting: a listed code; "other" needs the seller's own words (kept apart, never shown to the buyer)
        cancellation_reason = cancellation_note = None
        if body.status == "cancelled":
            cancellation_reason = body.cancellation_reason
            cancellation_note = (body.cancellation_note or "").strip() or None
            if cancellation_reason not in SELLER_CANCEL_REASONS or (cancellation_reason == OTHER_REASON and not cancellation_note):
                raise HTTPException(status_code=400, detail={"code": "invalid_reason", "message": "Pick a reason (write it for Other)"})

        # For "ready" + delivery: book Lalamove FIRST, only update status if booking succeeds
        booking_result = None
        if body.status == "ready" and order.get("delivery_method") == "delivery":
            from services.lalamove_service import get_lalamove_service
            from dao.dao_deliveries import DAODeliveries

            full_order = dao_orders.read_order_with_seller_coords(order_id)
            if not full_order:
                raise HTTPException(status_code=500, detail="Could not load order details for delivery")

            seller  = full_order.get("seller_profiles") or {}

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

            check_trip_addresses(full_order)
            pickup_address  = seller.get("address") or ""
            dropoff_address = full_order.get("delivery_address") or ""

            allingo = allingo_service.enabled()
            if not allingo:
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

            sender_phone = seller_phone(seller)
            recipient = lalamove_recipient(full_order)

            logger.warning(f"[Delivery] order={order_id} sender_phone={sender_phone} recipient_phone=…{recipient['recipient_phone'][-4:]}")

            booking_result = None
            last_booking_error = None
            attempts = DAOAdminConfig().get_positive_int("driver_booking_attempts", 3)
            taken = False
            if allingo:
                try:
                    booking_result, taken = book_allingo(full_order, sender_phone, recipient, attempts, until)
                except AllingoError as e:   # an empty wallet goes the failed-booking way too (admins already told)
                    last_booking_error = e
            else:
                for attempt in range(1, attempts + 1):
                    try:
                        result = service.place_order(
                            quotation_id=quotation.quotation_id,
                            stop_id_0=quotation.stop_id_0,
                            stop_id_1=quotation.stop_id_1,
                            sender_name=seller.get("store_name", "Seller"),
                            sender_phone=sender_phone,
                            **recipient,
                        )
                        booking_result = {"provider": "lalamove", "status": result.status, "trip_fee": quotation.total_fee,
                                          "lalamove_order_id": result.lalamove_order_id, "share_link": result.share_link}
                        break
                    except Exception as e:
                        last_booking_error = e
                        logger.warning(f"[Delivery] place_order attempt {attempt}/{attempts} failed for order={order_id}: {e}")

            if booking_result is None:
                logger.error(f"[Delivery] All {attempts} booking attempts failed for order={order_id}: {last_booking_error}")
                # The buyer UI translates this exact text (OrderStatusHeader.vue); no count in it, it's a setting
                # Conditional: the buyer may have cancelled (and been refunded) while the booking ran (T177 A32)
                if not dao_orders.update_order_status(order_id, "cancelled", NO_DRIVER_REASON,
                                                      expected_status=order["status"]):
                    raise HTTPException(status_code=409, detail="Order status changed, please refresh")
                from dao.dao_refunds import DAORefunds
                DAORefunds().create_refund_for_order(order, "driver_booking_failed")
                raise HTTPException(status_code=503, detail="Unable to book a delivery driver. Your order has been cancelled.")

            trip_id = booking_result.get("allingo_order_id") or booking_result["lalamove_order_id"]
            dao_deliveries = DAODeliveries()
            try:
                # A trip taken over from a double tap may already have its row (one row per trip id: the webhook reads one)
                written = taken and dao_deliveries.read_delivery_by_order_id(order_id)
                if not (written and written.get("allingo_order_id") == trip_id):
                    dao_deliveries.create_delivery(
                        order_id=order_id,
                        user_id=full_order.get("user_id"),
                        seller_user_id=full_order.get("seller_user_id"),
                        **booking_result,
                    )
            except Exception as db_err:
                # DB insert failed but the trip is already booked — roll back to avoid orphan.
                logger.error(f"[Delivery] create_delivery failed ({booking_result['provider']}={trip_id}); cancelling the trip")
                try:
                    if not cancel_trip(booking_result, get_lalamove_service, until):   # a False answer too (T191 TC-35)
                        logger.error(f"[Delivery] Rollback cancel failed for {trip_id} — MANUAL INTERVENTION NEEDED")
                except Exception as cancel_err:
                    logger.error(f"[Delivery] Rollback cancel failed for {trip_id}: {cancel_err} — MANUAL INTERVENTION NEEDED")
                if "deliveries_one_live_trip_per_order" in str(db_err):
                    # T180 A26: a second Ready at the same moment; the first one's trip is the order's (the DB keeps one)
                    raise HTTPException(status_code=409, detail="Order status changed, please refresh")
                raise HTTPException(status_code=500, detail=f"Failed to record delivery: {db_err}")
            logger.warning(f"[Delivery] Auto-booked order={order_id} {booking_result['provider']}={trip_id}")

        # Only update status after delivery booking succeeds (or if not a delivery order).
        # Conditional on the status read above: the confirm-timeout job or a buyer
        # cancelling a late order may have cancelled (and refunded) it in between.
        updated = dao_orders.update_order_status(order_id, body.status, cancellation_reason,
                                                 expected_status=order["status"], cancellation_note=cancellation_note)
        if not updated:
            # The trip was booked for an order that is no longer ours to send (R4.6).
            # It is still ASSIGNING_DRIVER, which the company lets us cancel.
            if booking_result and not keep_taken_trip(taken, dao_orders, order_id) and not cancel_trip(booking_result, get_lalamove_service, until):
                logger.error(f"[Delivery] order={order_id} changed while booking; cancel of {trip_id} failed — MANUAL INTERVENTION NEEDED")
            raise HTTPException(status_code=409, detail="Order status changed, please refresh")

        if body.status == "cancelled":
            from dao.dao_refunds import DAORefunds
            # Cancelling a failed delivery = no rider, not the seller's choice (T177 A32)
            DAORefunds().create_refund_for_order(order, "driver_booking_failed" if order["status"] == "delivery_failed" else "seller_cancel")

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
        return {"success": True, "menu": DAOFoodItems().read_menu_by_seller_id(seller_id),
                "option_groups": DAOMenuOptionGroups().read_store_groups(seller_id), "option_limits": _menu_limits()}
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
        if "daily_portions" in body.model_fields_set:   # null clears the daily limit
            fields["daily_portions"] = body.daily_portions
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        if "price" in fields:
            fields["price_text"] = _make_price_text(fields["price"])
        dao = DAOFoodItems()
        item = dao.update(item_id, seller_id, fields)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        dao.add_remaining_today([item])
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


# ── Option groups (seller-menu đợt 3, ADR 0003) ────────────────────────────────
# A store's groups are shared by its dishes. Every id in these routes is checked against the caller's store
# first and answers one 404 "Not found" otherwise (BM3); the composite FKs are the second line. Errors past
# the checks reach main.py's handler: a plain 500, no database text (QĐ3-5b).

MENU_LIMITS = {"menu_max_groups_per_dish": 10, "menu_max_options_per_group": 30,
               "menu_max_groups_per_store": 50, "menu_option_max_extra_price": 1_000_000}


def _menu_limits() -> dict:
    return DAOAdminConfig().get_positive_ints(MENU_LIMITS)


NAME_TAKEN = {"code": "option_name_taken", "message": "Two options have the same name"}


def _not_found():
    return HTTPException(status_code=404, detail="Not found")


def _limit_error(code: str, message: str, most: int):
    return HTTPException(status_code=400, detail={"code": code, "message": message, "max": most})


def _check_options(body, limits: dict, current: list) -> list:
    """The group's new option list as dicts, after the checks: given ids are options of this group, the
    count and the names, and the extra price cap for a price that is new or changed (an option saved under a
    higher cap keeps its price, TC3-67)."""
    by_id = {o["id"]: o for o in current}
    options = [o.model_dump() | {"id": str(o.id) if o.id else None} for o in body.options]
    if any(o["id"] and o["id"] not in by_id for o in options):
        raise _not_found()
    most = limits["menu_max_options_per_group"]
    if len(options) > most:
        raise _limit_error("options_max", f"At most {most} options in one group", most)
    names = [o["name"] for o in options]
    if len(set(names)) < len(names):
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    cap = limits["menu_option_max_extra_price"]
    if any(o["extra_price"] > cap and Decimal(str(by_id.get(o["id"], {}).get("extra_price", -1))) != o["extra_price"]
           for o in options):
        raise _limit_error("extra_price_max", f"An option can add at most {_make_price_text(cap)}", cap)
    return options


def _save_group(seller_id: str, group_id, body, current: list, limits: dict) -> dict:
    options = _check_options(body, limits, current)
    dao = DAOMenuOptionGroups()
    try:
        group_id = dao.save_group(seller_id, group_id, body.model_dump(exclude={"options"}), options)
    except OptionNameTaken:
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    return dao.read_group(group_id, seller_id)


@router.post("/me/menu/items/{item_id}/option-groups")
def create_option_group(item_id: uuid.UUID, body: Schema.RequestOptionGroup, user=Depends(verify_token)):
    """A new group, made from the dish form and put on that dish (Q4: groups are created from a dish)."""
    seller_id, item_id = _get_seller_id(user), str(item_id)
    dao = DAOMenuOptionGroups()
    if not DAOFoodItems().read_owned_by_seller(item_id, seller_id):
        raise _not_found()
    limits = _menu_limits()
    if dao.count_store_groups(seller_id) >= limits["menu_max_groups_per_store"]:
        most = limits["menu_max_groups_per_store"]
        raise _limit_error("groups_per_store_max", f"A store can have at most {most} option groups", most)
    links = dao.read_dish_links(item_id, seller_id)
    if len(links) >= limits["menu_max_groups_per_dish"]:
        most = limits["menu_max_groups_per_dish"]
        raise _limit_error("groups_per_dish_max", f"A dish can have at most {most} option groups", most)
    group = _save_group(seller_id, None, body, [], limits)
    dao.attach(item_id, group["id"], seller_id, len(links))
    group["dish_ids"] = [item_id]
    return {"success": True, "group": group}


@router.put("/me/menu/option-groups/{group_id}")
def update_option_group(group_id: uuid.UUID, body: Schema.RequestOptionGroup, user=Depends(verify_token)):
    """Name, required, how many, and the options (add / edit / turn off / remove): for every dish using it."""
    seller_id = _get_seller_id(user)
    current = DAOMenuOptionGroups().read_group(str(group_id), seller_id)
    if not current:
        raise _not_found()
    return {"success": True, "group": _save_group(seller_id, str(group_id), body, current["menu_options"], _menu_limits())}


@router.delete("/me/menu/option-groups/{group_id}")
def delete_option_group(group_id: uuid.UUID, user=Depends(verify_token)):
    """Only a group no dish uses (ADR 0003 point 11)."""
    seller_id, dao = _get_seller_id(user), DAOMenuOptionGroups()
    group = dao.read_group(str(group_id), seller_id)
    if not group:
        raise _not_found()
    if group["dish_ids"]:
        raise HTTPException(status_code=409, detail={"code": "group_in_use", "message": "Remove this group from its dishes first"})
    dao.delete_group(str(group_id), seller_id)
    return {"success": True}


def _owned_dish_and_group(item_id: str, group_id: str, seller_id: str):
    if not DAOFoodItems().read_owned_by_seller(item_id, seller_id) or not DAOMenuOptionGroups().read_group(group_id, seller_id):
        raise _not_found()


@router.post("/me/menu/items/{item_id}/option-groups/{group_id}")
def attach_option_group(item_id: uuid.UUID, group_id: uuid.UUID, user=Depends(verify_token)):
    seller_id, item_id, group_id = _get_seller_id(user), str(item_id), str(group_id)
    _owned_dish_and_group(item_id, group_id, seller_id)
    dao = DAOMenuOptionGroups()
    links = dao.read_dish_links(item_id, seller_id)
    if group_id not in links:
        most = _menu_limits()["menu_max_groups_per_dish"]
        if len(links) >= most:
            raise _limit_error("groups_per_dish_max", f"A dish can have at most {most} option groups", most)
        dao.attach(item_id, group_id, seller_id, len(links))
    return {"success": True}


@router.delete("/me/menu/items/{item_id}/option-groups/{group_id}")
def detach_option_group(item_id: uuid.UUID, group_id: uuid.UUID, user=Depends(verify_token)):
    """Takes the group off this dish; the group stays (ADR 0003 point 11)."""
    seller_id, item_id, group_id = _get_seller_id(user), str(item_id), str(group_id)
    _owned_dish_and_group(item_id, group_id, seller_id)
    dao = DAOMenuOptionGroups()
    dao.detach(item_id, group_id, seller_id)
    # The rest numbered 0..n-1 again: the next attach takes position n (len of the links)
    dao.set_dish_order(item_id, seller_id, dao.read_dish_links(item_id, seller_id))
    return {"success": True}


@router.put("/me/menu/items/{item_id}/option-groups")
def order_option_groups(item_id: uuid.UUID, body: Schema.RequestDishGroupOrder, user=Depends(verify_token)):
    """The dish's groups in a new order: the list must be exactly the groups the dish uses."""
    seller_id, item_id = _get_seller_id(user), str(item_id)
    if not DAOFoodItems().read_owned_by_seller(item_id, seller_id):
        raise _not_found()
    dao = DAOMenuOptionGroups()
    group_ids = [str(g) for g in body.group_ids]
    if sorted(group_ids) != sorted(dao.read_dish_links(item_id, seller_id)):
        raise HTTPException(status_code=400, detail="The list must hold every group of this dish once")
    dao.set_dish_order(item_id, seller_id, group_ids)
    return {"success": True}


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
        # payout-auto: weekly periods, paid on a weekday once the complaint window is over
        weeks = config.get_int_in_range("payout_period_weeks", 1, 1, 4)
        weekday = config.get_int_in_range("payout_weekday", 2, 1, 7)
        hour = config.get_int_in_range("payout_generate_hour", 8, 0, 23)
        window_hours = config.get_positive_int("complaint_window_hours", 24)
        max_percent = min(config.get_positive_int("payout_deduction_max_percent", 100), 100)
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=history_days)

        orders, waiting = [], Decimal(0)
        for row in DAOOrders().read_done_orders_for_earnings(seller_id, since):
            # What reaches the seller: the order's payout minus the tax withheld from it
            payout = _money(row.get("payout_amount"))
            withheld = _money(row.get("wh_vat_amount")) + _money(row.get("wh_pit_amount"))
            state = row.get("payout_status") or "pending"
            if state == "pending" and row.get("payout_hold"):
                state = "held"
            expected = None
            if state == "pending":
                waiting += payout - withheld
                done_at = datetime.fromisoformat(row["status_changed_at"])
                expected = expected_payout_date(done_at, weeks, weekday, hour, window_hours, now).isoformat()
            orders.append({
                "id": row["id"],
                "done_at": row.get("status_changed_at"),
                "subtotal": _vnd(_money(row.get("subtotal"))),
                "commission_amount": _vnd(_money(row.get("commission_amount"))),
                "vat_amount": _vnd(_money(row.get("vat_amount"))),
                "payout_amount": _vnd(payout),
                "wh_vat_amount": _vnd(_money(row.get("wh_vat_amount"))),   # 0 until computed
                "wh_pit_amount": _vnd(_money(row.get("wh_pit_amount"))),
                "net_amount": _vnd(payout - withheld),   # T174 A7: what the seller gets for it
                "payout_state": state,
                # T181 A51: the complaint that holds it ("complaint KN000012"), so the store knows which one to settle
                "hold_complaint": (row.get("payout_hold_note") or "").removeprefix("complaint ") or None if state == "held" else None,
                "expected_payout_date": expected,
            })

        # T174 A9: open deductions come off what is waiting the way the next payout takes them
        # (admin_generate_payout_for_seller step 7): at most payout_deduction_max_percent of it, the rest waits.
        dao_payouts = DAOAdminPayouts()
        open_list = dao_payouts.read_open_deductions(seller_id)
        open_deductions = sum((_money(d["amount"]) - _money(d["applied_amount"]) for d in open_list), Decimal(0))
        taken = min(open_deductions, (waiting * max_percent / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        # orders already in a payout (state processing) count at its net: their deductions are taken, not open
        awaiting, deducted = waiting - taken, taken

        payouts, received = [], Decimal(0)
        for row in dao_payouts.read_payouts_by_seller_id(seller_id, EARNINGS_PAYOUTS_LIMIT):
            net = _money(row.get("net_payout"))
            if row.get("status") == "completed":
                received += net
            elif row.get("status") in ("pending", "processing"):
                awaiting += net
                deducted += _money(row.get("total_deductions"))
            payouts.append({
                **row,
                "net_payout": _vnd(net),
                "withholding_amount": _vnd(_money(row.get("withholding_amount"))),
                "total_deductions": _vnd(_money(row.get("total_deductions"))),
            })

        return {
            "success": True,
            "history_days": history_days,
            "awaiting_total": _vnd(awaiting),
            "deductions_total": _vnd(deducted),                    # comes off the orders awaiting payout
            "deductions_carry": _vnd(open_deductions - taken),     # left for a later payout
            # T181 A51: each open deduction: what kind (a refund charged to the store, or a fee), which order, what is left
            "deductions": [{"order_id": d["order_id"], "kind": "refund" if d.get("refund_id") else "fee",
                            "amount": _vnd(_money(d["amount"]) - _money(d["applied_amount"]))} for d in open_list],
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