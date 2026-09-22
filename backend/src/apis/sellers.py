import logging

from dao.dao_seller_profiles import DAOSellerProfiles
from dao.dao_food_items import DAOFoodItems
from dao.dao_menu_categories import DAOMenuCategories
from dao.dao_reviews import DAOReviews

from fastapi import APIRouter, HTTPException, Depends, Query, status

from apis.reviews import mask_reviewer
from core.auth import verify_token
from core.phone import to_e164_vn
from dao.dao_orders import DAOOrders
from schemas import Schema
from utils.storage import upload_image_base64

router = APIRouter(prefix="/sellers")
logger = logging.getLogger(__name__)


VALID_STATUS_TRANSITIONS = {
    "pending":          ["confirmed", "cancelled"],
    "confirmed":        ["ready", "cancelled"],
    "ready":            ["done", "cancelled"],  # delivery_failed is set by webhook only, not by seller
    "delivery_failed":  ["done", "cancelled"],
}


@router.get("/")
def get_sellers(user=Depends(verify_token)):
    pass


@router.get("/founding")
def get_founding_sellers():

    dao_seller_profiles = DAOSellerProfiles()
    sellers = dao_seller_profiles.read_founding_sellers()

    return {"success": True, "founding_sellers": sellers}


# ── Seller Dashboard Endpoints (must be before /{slug_name} wildcard) ──

def _get_seller_id(user):
    dao = DAOSellerProfiles()
    profile = dao.read_seller_profile_by_user_id(user["id"])
    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a seller")
    return profile["id"]


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
            "phone": profile.get("phone"),
            "has_address": bool(profile.get("address") and profile.get("lat") and profile.get("lon")),
            "has_phone": bool(profile.get("phone")),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))\
        

@router.get("/me/orders")
def get_seller_orders(user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        dao_orders = DAOOrders()
        orders = dao_orders.read_orders_by_seller_id(seller_id)
        return {"success": True, "orders": orders, "seller_id": seller_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/orders: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/orders/{order_id}")
def get_seller_order_detail(order_id: str, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        dao_orders = DAOOrders()
        order = dao_orders.read_order_by_id_for_seller(order_id, seller_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"success": True, "order": order}
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

        # Pass cancellation_reason when rejecting
        cancellation_reason = body.cancellation_reason if body.status == "cancelled" else None

        # For "ready" + delivery: book Lalamove FIRST, only update status if booking succeeds
        if body.status == "ready" and order.get("delivery_method") == "delivery":
            from services.lalamove_service import get_lalamove_service
            from dao.dao_deliveries import DAODeliveries

            full_order = dao_orders.read_order_with_seller_coords(order_id)
            if not full_order:
                raise HTTPException(status_code=500, detail="Could not load order details for delivery")

            seller  = full_order.get("seller_profiles") or {}
            buyer   = full_order.get("users") or {}

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
                raise HTTPException(status_code=400, detail=f"Seller phone invalid: {e}. Update store phone in settings.")
            try:
                recipient_phone = to_e164_vn(buyer.get("phone") or "")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Buyer phone invalid: {e}. Buyer must update phone before delivery.")

            logger.warning(f"[Delivery] order={order_id} sender_phone={sender_phone} recipient_phone={recipient_phone}")

            booking_result = None
            last_booking_error = None
            for attempt in range(1, 4):
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
                    logger.warning(f"[Delivery] place_order attempt {attempt}/3 failed for order={order_id}: {e}")

            if booking_result is None:
                logger.error(f"[Delivery] All 3 booking attempts failed for order={order_id}: {last_booking_error}")
                dao_orders.update_order_status(order_id, "cancelled", "Driver booking failed after 3 attempts")
                if order.get("payment_status") == "paid":
                    from dao.dao_refunds import DAORefunds
                    try:
                        DAORefunds().create_refund(
                            order_id=order_id,
                            amount=order["total_amount"],
                            reason="driver_booking_failed",
                            original_txn_ref=order.get("transaction_ref"),
                            ipn_data=order.get("ipn_data"),
                            payment_create_date=order.get("payment_create_date"),
                        )
                    except Exception as re:
                        logger.warning(f"Failed to create refund record for order {order_id}: {re}")
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

        # Only update status after delivery booking succeeds (or if not a delivery order)
        updated = dao_orders.update_order_status(order_id, body.status, cancellation_reason)

        return {"success": True, "order": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/orders/{order_id}/status: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))



def _make_price_text(price: float) -> str:
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
    except Exception as e:
        logger.exception(f"Exception in PATCH /sellers/me/menu/items/{item_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me/menu/items/{item_id}/image")
def upload_food_item_image(item_id: str, body: Schema.RequestUploadImage, user=Depends(verify_token)):
    try:
        seller_id = _get_seller_id(user)
        path = f"food-items/{seller_id}/{item_id}"
        image_url = upload_image_base64(path, body.image_base64, body.content_type or "image/jpeg")
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
            food_item = review.pop("food_items", None) or {}
            # None on overall rows — the frontend labels those as a whole-order rating.
            review["food_item_name"] = food_item.get("name")

        return {"success": True, "reviews": reviews}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Exception in GET /sellers/me/reviews: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/featured-dishes")
def get_featured_dishes():
    try:
        dao = DAOFoodItems()
        dishes = dao.read_featured_dishes()
        print(dishes)
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