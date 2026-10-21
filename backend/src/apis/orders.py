import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
)

from apis.complaints import complaints_for_order
from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_carts import DAOCarts
from dao.dao_cart_items import DAOCartItems
from dao.dao_orders import DAOOrders
from dao.dao_order_items import DAOOrderItems
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from services import push_service
from services.lalamove_service import get_lalamove_service
from utils.pricing import order_amounts

router = APIRouter(prefix="/orders")
logger = logging.getLogger(__name__)


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
        if food.get("is_available") is False:
            names.append(food.get("name"))
        elif variant and variant.get("is_available") is False:
            names.append(f"{food.get('name')} ({variant.get('name')})")
    return names


# Shared with POST /cart/add. A closed store still takes pre-orders (delivered on a later
# day); only same-day dishes (preorder_day 0) are blocked.
STORE_CLOSED_DETAIL = "This store is closed now. Same-day dishes can't be ordered; pre-order dishes still can."


def is_same_day(preorder_day) -> bool:
    return not preorder_day  # 0 / None


def same_day_names(cart_items: list) -> list:
    return [(item.get("food_items") or {}).get("name") for item in cart_items
            if is_same_day((item.get("food_items") or {}).get("preorder_day"))]


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
        import datetime
        now = datetime.datetime.utcnow()
        for r in recent:
            if r["seller_id"] == cart["seller_id"] and r["status"] == "pending":
                created = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00").replace("+00:00", ""))
                if (now - created).total_seconds() < 60:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate order detected. Please wait.")

    # 2. Check the cart is still sellable
    cart_items = cart["cart_items"]

    sold_out = unavailable_names(cart_items)
    if sold_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_longer_available", "message": f"No longer available: {', '.join(sold_out)}",
                    "names": ", ".join(sold_out)},
        )

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
            quote = get_lalamove_service().get_quotation(
                pickup_lat=float(seller_info["lat"]),
                pickup_lon=float(seller_info["lon"]),
                pickup_address=seller_info["address"] or "Pickup",
                dropoff_lat=request.delivery_lat,
                dropoff_lon=request.delivery_lon,
                dropoff_address=request.delivery_address,
            )
        except Exception as e:
            logger.exception(f"Lalamove quotation failed in POST /orders: {e}")
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
        delivery_appointment=request.delivery_appointment,
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


SELLER_LATE_REASON = "Seller was late"  # the buyer UI translates this exact text (OrderStatusHeader.vue)


def _ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def cancel_after(order: dict):
    """When the buyer may cancel a late order with a full refund (R4, R6 in
    docs/dev/order-cancel-refund.md), or None if this status has no such deadline.
    Nothing auto-cancels: past the deadline the buyer chooses to wait or cancel."""
    changed = _ts(order.get("status_changed_at"))
    if order["status"] == "confirmed":
        appointment = _ts(order.get("delivery_appointment"))
        return (appointment or changed) + DAOAdminConfig().get_minutes("buyer_cancel_late_confirmed_minutes", 60)
    if order["status"] == "delivery_failed":
        return changed + DAOAdminConfig().get_minutes("buyer_cancel_late_delivery_failed_minutes", 30)
    return None


@router.get("/{order_id}")
def get_order_detail(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    deadline = cancel_after(order)
    order["cancel_after"] = deadline.isoformat() if deadline else None
    order |= complaints_for_order(order, user["id"], "buyer")   # T35
    return {"success": True, "order": order}


@router.patch("/{order_id}/cancel")
def cancel_order(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    now = datetime.now(timezone.utc)
    reason = None
    if order["status"] == "pending":
        appointment = _ts(order.get("delivery_appointment"))
        if appointment:
            cutoff = DAOAdminConfig().get_minutes("buyer_cancel_before_appointment_minutes", 1440)
            if appointment - now < cutoff:
                hours = f"{cutoff.total_seconds() / 3600:g}"
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                    "code": "cancel_cutoff", "hours": hours,
                    "message": f"Can't cancel within {hours} hours of the delivery time"})
    else:
        deadline = cancel_after(order)
        if not deadline or now < deadline:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order can't be cancelled now")
        reason = SELLER_LATE_REASON

    # Conditional: the seller may have moved the order on (e.g. tapped Ready) since we read it
    updated = dao_orders.update_order_status(order_id=order_id, status="cancelled", cancellation_reason=reason,
                                             expected_status=order["status"])
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order status changed, please refresh")
    push_service.notify_buyer_cancelled(updated)

    from dao.dao_refunds import DAORefunds
    DAORefunds().create_refund_for_order(order, "buyer_cancel")

    return {"success": True}
