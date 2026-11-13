import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
)

from apis.complaints import complaints_for_order
from apis.deliveries import quote_trip
from core.auth import verify_token
from core.phone import to_e164_vn
from core.store_hours import VN_TZ, confirm_deadline, is_open_now
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_carts import DAOCarts
from dao.dao_cart_items import DAOCartItems
from dao.dao_orders import DAOOrders
from dao.dao_order_items import DAOOrderItems
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from services import push_service
from services.order_expiry import confirm_window
from services.lalamove_service import get_lalamove_service
from utils.pricing import chosen_options, dish_groups, options_sold_out, order_amounts
from utils.stock import min_qty, stock_error, stock_sold_out

router = APIRouter(prefix="/orders")
logger = logging.getLogger(__name__)


def one_line(text):
    """None for blank; newlines, tabs and other control characters become one space (TC-14, TC-15)."""
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", text or "").split()) or None


def unavailable_names(cart_items: list) -> list:
    """Dishes (or levels) in the cart that the seller has since stopped selling.

    The cart holds live references, so a dish or level can go off sale between
    "add to cart" and "place order". Creating the order anyway sells something
    the seller no longer offers.
    """
    names = []
    for item in cart_items:
        food = item.get("food_items") or {}
        variant = item.get("food_item_variants")
        if food.get("is_available") is False or stock_sold_out(food):   # fewer left than one order takes (QĐ2-7)
            names.append(food.get("name"))
        elif variant and variant.get("is_available") is False:
            names.append(f"{food.get('name')} ({variant.get('name')})")
    return names


def max_per_dish() -> int:
    return DAOAdminConfig().get_positive_int("cart_max_quantity_per_item", 50)


def max_lines() -> int:
    return DAOAdminConfig().get_positive_int("cart_max_lines", 20)


def quantity_max_error(most: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
        "code": "quantity_max", "message": f"At most {most} of each dish", "max": most})


def lines_max_error(most: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
        "code": "cart_max_lines", "message": f"At most {most} different dishes in one cart", "max": most})


def check_quantities(quantities) -> None:
    """400 when one dish (all its cart rows: price options and option choices together) asks more than
    cart_max_quantity_per_item. A bot put ~22 billion ₫ orders through with no cap (docs/dev/20261102-security-fixes S1)."""
    most = max_per_dish()
    if max(quantities, default=0) > most:
        raise quantity_max_error(most)


def dish_totals(cart_items: list) -> dict:
    """{food_item_id: quantity of the dish over all its cart rows}."""
    totals = {}
    for item in cart_items:
        food_id = (item.get("food_items") or {}).get("id")
        totals[food_id] = totals.get(food_id, 0) + item["quantity"]
    return totals


def option_problem(cart_item: dict):
    """None, or the error detail of a cart row's options (QĐ3-4), the one check of POST /cart/add, GET /cart and
    POST /orders. options_sold_out means the dish can't be ordered at all (409); the others ask the buyer to
    choose again (400). The row's option_ids are already de-duplicated (add_cart_item)."""
    food = cart_item["food_items"]
    dish = food.get("name")
    if options_sold_out(food):
        return {"code": "options_sold_out", "message": f"Sold out: {dish}", "name": dish}
    chosen = chosen_options(cart_item)
    if len(chosen) < len(set(cart_item.get("option_ids") or [])):
        return {"code": "option_unknown", "message": f"Some choices for {dish} are no longer offered. Please choose again.",
                "name": dish}
    off = next((o for _, o in chosen if not o["is_available"]), None)
    if off:
        return {"code": "option_unavailable", "message": f"{off['name']} is no longer available. Please choose again.",
                "name": dish, "option": off["name"]}
    for group in dish_groups(food):
        picked = sum(1 for g, _ in chosen if g["id"] == group["id"])
        if group["is_required"] and not picked:
            return {"code": "option_required", "message": f"Choose an option in {group['name']} for {dish}",
                    "name": dish, "group": group["name"]}
        if picked > group["max_select"]:
            return {"code": "option_max", "message": f"Choose at most {group['max_select']} in {group['name']} for {dish}",
                    "name": dish, "group": group["name"], "max": group["max_select"]}
    return None


def option_error(problem: dict) -> HTTPException:
    code = status.HTTP_409_CONFLICT if problem["code"] == "options_sold_out" else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=problem)


# Shared with POST /cart/add. A closed store still takes pre-orders (delivered on a later
# day); only same-day dishes (preorder_day 0) are blocked.
STORE_CLOSED_DETAIL = "This store is closed now. Same-day dishes can't be ordered; pre-order dishes still can."


def is_same_day(preorder_day) -> bool:
    return not preorder_day  # 0 / None


def same_day_names(cart_items: list) -> list:
    return [(item.get("food_items") or {}).get("name") for item in cart_items
            if is_same_day((item.get("food_items") or {}).get("preorder_day"))]


# T127: a cart with a pre-order dish (preorder_day > 0) needs a delivery appointment at least that many days
# ahead, the cart page's rule (TotalAmounts.vue: now + the cart's largest preorder_day). The grace covers the
# minutes between the cart page computing its minimum and the order reaching us (a buyer who keeps the page
# open, latency): a technical tolerance, not a business rule.
APPOINTMENT_GRACE = timedelta(minutes=30)


def appointment_error(cart_items: list, appointment, now: datetime):
    """None, or the 400 detail for a pre-order cart without a valid appointment. A naive time is Vietnam time."""
    days = max(((item.get("food_items") or {}).get("preorder_day") or 0 for item in cart_items), default=0)
    if days <= 0:
        return None
    if appointment is None:
        return {"code": "appointment_required", "message": "Choose a delivery date and time for pre-order dishes", "days": days}
    when = appointment if appointment.tzinfo else appointment.replace(tzinfo=VN_TZ)
    if when <= now:
        return {"code": "appointment_past", "message": "The delivery time has already passed", "days": days}
    if when < now + timedelta(days=days) - APPOINTMENT_GRACE:
        return {"code": "appointment_too_early", "message": f"Pre-order dishes need at least {days} day(s)", "days": days}
    return None


@router.post("")
def create_order(request: Schema.RequestCreateOrder, user=Depends(verify_token)):

    user_id = user["id"]

    # 1. Get user's cart with items
    dao_cart_items = DAOCartItems()
    cart = dao_cart_items.read_cart_items_by_user_id(user_id=user_id)

    if not cart or not cart.get("cart_items"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    # Idempotency: check if user has a pending order from same seller created in last 60s
    dao_orders = DAOOrders()
    recent = dao_orders.read_orders_by_user_id(user_id=user_id)
    if recent:
        now = datetime.utcnow()
        for r in recent:
            if r["seller_id"] == cart["seller_id"] and r["status"] == "pending":
                created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00").replace("+00:00", ""))
                if (now - created).total_seconds() < 60:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate order detected. Please wait.")

    # 2. Check the cart is still sellable
    cart_items = cart["cart_items"]
    # A cart filled before the caps existed, or two adds that raced past them (TC3-65)
    check_quantities(dish_totals(cart_items).values())
    if len(cart_items) > (most := max_lines()):
        raise lines_max_error(most)
    # The cart's store, not the dish's, was chosen by the client at /cart/add before this check existed (BM2)
    if any((item.get("food_items") or {}).get("seller_id") != cart["seller_id"] for item in cart_items):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart contains a dish of another store")

    appointment = request.delivery_appointment
    if appointment is not None and appointment.tzinfo is None:
        appointment = appointment.replace(tzinfo=VN_TZ)   # stored as a real moment, not read as UTC
    bad_appointment = appointment_error(cart_items, appointment, datetime.now(timezone.utc))
    if bad_appointment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=bad_appointment)

    # The driver calls this number (delivery-recipient R2): checked now, not when the seller books the trip
    receiver = {}
    if request.delivery_method == "delivery":
        receiver = {key: one_line(getattr(request, key)) for key in ("receiver_name", "receiver_phone", "delivery_note")}
    if receiver.get("receiver_phone"):
        try:
            receiver["receiver_phone"] = to_e164_vn(receiver["receiver_phone"])
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "code": "receiver_phone_invalid",
                "message": "The receiver's phone number is not a valid Vietnamese number. Please fix it in your address.",
            })

    sold_out = unavailable_names(cart_items)
    if sold_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_longer_available", "message": f"No longer available: {', '.join(sold_out)}",
                    "names": ", ".join(sold_out)},
        )

    for item in cart_items:
        problem = option_problem(item)
        if problem:
            raise option_error(problem | {"cart_item_id": item["id"]})

    # Sold out (above), then short of stock, then under the minimum per order (QĐ2-12), each over all of a dish's rows
    wanted = dish_totals(cart_items)
    foods = {(item.get("food_items") or {}).get("id"): item.get("food_items") or {} for item in cart_items}
    short = stock_error(wanted, foods)
    if short:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=short)
    low = next((foods[f] for f, qty in wanted.items() if qty < min_qty(foods[f])), None)
    if low:   # QĐ2-9: only here; the cart lets a buyer split it (1 Coca + 1 Pepsi)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": "min_quantity", "message": f"At least {min_qty(low)} of {low.get('name')} in one order",
            "name": low.get("name"), "min": min_qty(low)})

    # 3. Get seller user_id + effective commission rate in one query
    dao_seller_profile = DAOSellerProfiles()
    seller_info = dao_seller_profile.read_seller_order_info(cart["seller_id"])
    if not seller_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seller not found")

    # Items may have entered the cart before the seller closed
    if not seller_info["is_open"] and same_day_names(cart_items):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=STORE_CLOSED_DETAIL)

    # Delivery fee is quoted here, never taken from the client (R1, docs/dev/order-cancel-refund.md).
    # A fee that differs from what the buyer saw → 409 with the new fee; the cart shows it and they re-place.
    delivery_fee, quotation_id = None, None
    if request.delivery_method == "delivery":
        if not seller_info["lat"] or not seller_info["lon"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seller location not configured")
        try:
            quote = quote_trip(
                get_lalamove_service, seller_info, user_id, receiver,
                pickup_lat=float(seller_info["lat"]),
                pickup_lon=float(seller_info["lon"]),
                pickup_address=seller_info["address"] or "Pickup",
                dropoff_lat=request.delivery_lat,
                dropoff_lon=request.delivery_lon,
                dropoff_address=request.delivery_address,
            )
        except HTTPException:   # a missing phone for AllinGo's contacts (T191): its own 400
            raise
        except Exception as e:
            logger.exception(f"Delivery quotation failed in POST /orders: {e}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail="Could not get a delivery fee quote. Please try again.")
        delivery_fee, quotation_id = quote.total_fee, quote.quotation_id
        if Decimal(str(request.delivery_fee or 0)) != delivery_fee:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "code": "delivery_fee_changed",
                "message": "Delivery fee has changed",
                "delivery_fee": delivery_fee,
                "quotation_id": quotation_id,
            })

    # Money columns, Decimal (snapshot seller's rate at order time)
    commission_rate = seller_info["commission_rate"]
    vat_rate = DAOAdminConfig().get_tax_rate("vat_rate")
    amounts = order_amounts(cart_items, commission_rate, vat_rate, delivery_fee)

    # 4. Create order (include delivery fields if present)
    order = dao_orders.create_order(
        user_id=user_id,
        seller_id=cart["seller_id"],
        seller_user_id=seller_info["user_id"],
        commission_rate=commission_rate,
        vat_rate=vat_rate,
        **amounts,
        delivery_method=request.delivery_method,
        delivery_address=request.delivery_address,
        note=request.note,
        delivery_lat=request.delivery_lat,
        delivery_lon=request.delivery_lon,
        delivery_fee=delivery_fee,
        quotation_id=quotation_id,
        delivery_appointment=appointment,
        **receiver,
    )

    if not order:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create order")

    # 5. Copy cart items → order items (snapshot). Rollback order if fails.
    try:
        dao_order_items = DAOOrderItems()
        dao_order_items.create_order_items_from_cart(order_id=order["id"], cart_items=cart_items)
    except Exception as e:
        dao_orders.update_order_status(order_id=order["id"], status="cancelled")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create order items")

    # 6. Clear cart (best-effort — order already committed)
    try:
        dao_cart = DAOCarts()
        dao_cart.delete_cart(cart_id=cart["id"])
    except Exception as e:
        logger.warning(f"Failed to clear cart after order {order['id']}: {e}")

    return {"success": True, "order": order}


@router.get("")
def get_orders(user=Depends(verify_token)):

    dao_orders = DAOOrders()
    orders = dao_orders.read_orders_by_user_id(user_id=user["id"])

    return {"success": True, "orders": orders}


# orders.cancellation_reason codes (T178): each viewer's app translates them (frontend utils/cancelReason.js)
SELLER_LATE_REASON = "seller_late"            # the buyer cancelled a late order
DELIVERY_FAILED_REASON = "delivery_failed"    # the buyer cancelled a failed delivery: the company failed, not the seller (T177)
BUYER_CANCELLED_REASON = "buyer_cancelled"    # the buyer cancelled an order still pending (A31)


def _ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def cancel_after(order: dict, get_minutes=None):
    """When the buyer may cancel a late order with a full refund (R4, R6 in
    docs/dev/order-cancel-refund.md), or None if this status has no such deadline.
    Nothing auto-cancels: past the deadline the buyer chooses to wait or cancel.
    get_minutes: a list passes one cached settings reader, so each setting is read once per request."""
    get_minutes = get_minutes or DAOAdminConfig().get_minutes
    changed = _ts(order.get("status_changed_at"))
    if order["status"] == "confirmed":
        appointment = _ts(order.get("delivery_appointment"))
        return (appointment or changed) + get_minutes("buyer_cancel_late_confirmed_minutes", 60)
    if order["status"] == "delivery_failed":
        return changed + get_minutes("buyer_cancel_late_delivery_failed_minutes", 30)
    return None


def cancel_before(order: dict):
    """A pending order with a delivery time: the last moment the buyer may cancel it
    (buyer_cancel_before_appointment_minutes before that time, R3.3), or None if no such limit."""
    appointment = _ts(order.get("delivery_appointment"))
    if order["status"] != "pending" or not appointment:
        return None
    return appointment - DAOAdminConfig().get_minutes("buyer_cancel_before_appointment_minutes", 1440)


def confirm_by(order: dict):
    """A paid order the seller has not accepted: when it auto-cancels, as the seller sees it (_with_deadlines).
    None while the store is closed, that clock is paused. The store's hours are read here and not sent on."""
    seller = order.get("seller_profiles") or {}
    hours, opened_at = seller.pop("weekly_hours", None), seller.pop("opened_at", None)
    switch = seller.pop("is_open", None)
    if order["status"] != "pending" or order.get("payment_status") != "paid" or not order.get("paid_at"):
        return None
    now = datetime.now(timezone.utc)
    if not is_open_now(switch, hours, now, order["seller_id"]):
        return None
    return confirm_deadline(_ts(order["paid_at"]), hours, _ts(opened_at) if opened_at else None, now, confirm_window(),
                            order["seller_id"])


@router.get("/{order_id}")
def get_order_detail(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    deadline = cancel_after(order)
    order["cancel_after"] = deadline.isoformat() if deadline else None
    last = cancel_before(order)
    order["cancel_before"] = last.isoformat() if last else None
    confirm = confirm_by(order)
    order["confirm_by"] = confirm.isoformat() if confirm else None   # A29
    order |= complaints_for_order(order, user["id"], "buyer")   # T35
    return {"success": True, "order": order}


@router.patch("/{order_id}/cancel")
def cancel_order(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    now = datetime.now(timezone.utc)
    reason, refund_reason = BUYER_CANCELLED_REASON, "buyer_cancel"
    if order["status"] == "pending":
        last = cancel_before(order)
        if last and now > last:
            hours = f"{(_ts(order['delivery_appointment']) - last).total_seconds() / 3600:g}"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "code": "cancel_cutoff", "hours": hours,
                "message": f"Can't cancel within {hours} hours of the delivery time"})
    else:
        deadline = cancel_after(order)
        if not deadline or now < deadline:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order can't be cancelled now")
        reason = SELLER_LATE_REASON
        if order["status"] == "delivery_failed":   # no rider: the seller's cancel of it gets the same refund reason (A32)
            reason, refund_reason = DELIVERY_FAILED_REASON, "driver_booking_failed"

    # Conditional: the seller may have moved the order on (e.g. tapped Ready) since we read it
    updated = dao_orders.update_order_status(order_id=order_id, status="cancelled", cancellation_reason=reason,
                                             expected_status=order["status"])
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order status changed, please refresh")
    push_service.notify_buyer_cancelled(updated)

    from dao.dao_refunds import DAORefunds
    DAORefunds().create_refund_for_order(order, refund_reason)

    return {"success": True}
