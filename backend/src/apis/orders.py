import logging

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
)

from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_carts import DAOCarts
from dao.dao_cart_items import DAOCartItems
from dao.dao_orders import DAOOrders
from dao.dao_order_items import DAOOrderItems
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from services import push_service
from utils.pricing import cart_item_unit_price

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

    # 2. Calculate subtotal + commission (snapshot seller's rate at order time)
    cart_items = cart["cart_items"]

    sold_out = unavailable_names(cart_items)
    if sold_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No longer available: {', '.join(sold_out)}",
        )
    subtotal = sum(
        cart_item_unit_price(item) * item["quantity"]
        for item in cart_items
    )
    total_amount = subtotal + float(request.delivery_fee or 0)

    # 3. Get seller user_id + effective commission rate in one query
    dao_seller_profile = DAOSellerProfiles()
    seller_info = dao_seller_profile.read_seller_order_info(cart["seller_id"])
    if not seller_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seller not found")

    commission_rate = seller_info["commission_rate"]
    commission_amount = round(subtotal * commission_rate, 2)

    vat_rate = DAOAdminConfig().get_tax_rate("vat_rate")
    vat_amount = round(commission_amount * vat_rate, 2)

    payout_amount = round(subtotal - commission_amount - vat_amount, 2)

    # 4. Create order (include delivery fields if present)
    order = dao_orders.create_order(
        user_id=user_id,
        seller_id=cart["seller_id"],
        seller_user_id=seller_info["user_id"],
        subtotal=subtotal,
        total_amount=total_amount,
        commission_rate=commission_rate,
        commission_amount=commission_amount,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        payout_amount=payout_amount,
        delivery_method=request.delivery_method,
        delivery_address=request.delivery_address,
        note=request.note,
        delivery_lat=request.delivery_lat,
        delivery_lon=request.delivery_lon,
        delivery_fee=request.delivery_fee,
        quotation_id=request.quotation_id,
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


@router.get("/{order_id}")
def get_order_detail(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return {"success": True, "order": order}


@router.patch("/{order_id}/cancel")
def cancel_order(order_id: str, user=Depends(verify_token)):

    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=order_id, user_id=user["id"])

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending orders can be cancelled")

    if order.get("delivery_appointment"):
        import datetime as dt
        appt = dt.datetime.fromisoformat(order["delivery_appointment"].replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        if (appt - now).total_seconds() < 86400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể hủy đơn trong vòng 24 giờ trước giờ hẹn")

    updated = dao_orders.update_order_status(order_id=order_id, status="cancelled")
    if updated:
        push_service.notify_buyer_cancelled(updated)

    if order.get("payment_status") == "paid":
        from dao.dao_refunds import DAORefunds
        try:
            DAORefunds().create_refund(
                order_id=order_id,
                amount=order["total_amount"],
                reason="buyer_cancel",
                original_txn_ref=order.get("transaction_ref"),
                ipn_data=order.get("ipn_data"),
                payment_create_date=order.get("payment_create_date"),
            )
        except Exception as e:
            logger.warning(f"Failed to create refund record for order {order_id}: {e}")

    return {"success": True}
