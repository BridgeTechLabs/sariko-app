import datetime
import uuid
import traceback
from typing import List, Optional
import json
import logging

from dao.dao_cart_items import CartLimit, DAOCartItems
from dao.dao_carts import DAOCarts
from dao.dao_food_item_variants import DAOFoodItemVariants
from dao.dao_food_items import DAOFoodItems
from apis.orders import (STORE_CLOSED_DETAIL, check_quantities, is_same_day, lines_max_error, max_lines,
                         max_per_dish, option_error, option_problem, portions_error, quantity_max_error)
from core.store_hours import VN_TZ, is_open_now
from core.seller_status import with_buyer_status
from utils.pricing import cart_item_unit_price, options_snapshot
from schemas import Schema

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
    Query, 
    Response
)

from core.auth import verify_token
from dao.dao_users import DAOUsers

router = APIRouter(prefix="/cart")
logger = logging.getLogger(__name__)

@router.get("")
def get_current_cart(user=Depends(verify_token)):
        
    dao_cart_items = DAOCartItems()
    cart = dao_cart_items.read_cart_items_by_user_id(user_id=user["id"])
    if cart:   # T181 A49: the portions left, so the cart can show a dish that has fewer than the buyer wants
        DAOFoodItems().add_remaining_today([ci["food_items"] for ci in cart["cart_items"]])
        # Priced here, the cart shows what POST /orders charges (QĐ3-3c); a row whose options no longer fit
        # carries the problem POST /orders would refuse it with, so the buyer can choose again first.
        for line in cart["cart_items"]:
            line["unit_price"] = cart_item_unit_price(line)
            line["options"] = options_snapshot(line) or []
            line["problem"] = option_problem(line)
    return {"success": True, "cart": cart}


def _validate_variant(food_item_id: str, variant_id: Optional[str]):
    """Reject a cart write whose price option does not match the dish.

    Without this a dish that HAS price options could enter the cart with
    variant_id = NULL, and POST /orders would then price it from food_items.price
    — a number that means nothing once options exist.
    """
    variants = DAOFoodItemVariants().read_by_food_item_id(food_item_id)

    if not variants:
        if variant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This dish has no price options")
        return

    if not variant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please choose a price option")

    chosen = next((v for v in variants if v["id"] == variant_id), None)
    if not chosen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid price option for this dish")
    if not chosen["is_available"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This price option is sold out")


@router.post("/add")
def add_item_to_cart(request: Schema.RequestAddCartItem, user=Depends(verify_token)):
    
    user_id = user["id"]
    check_quantities([request.quantity])
    _validate_variant(request.food_item_id, request.variant_id)

    gate = DAOFoodItems().read_order_gate(request.food_item_id)
    if not gate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dish not found")
    # The cart's store comes from the dish, not from the client (BM2)
    if gate["seller_id"] != request.seller_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This dish is not on this store's menu")
    # Off sale ("Đang bán" off): shown as Sold out in the menu; POST /orders would refuse it anyway
    if gate.get("is_available") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This dish is sold out")
    option_ids = sorted({str(i) for i in request.option_ids})
    problem = option_problem({"food_items": gate, "option_ids": option_ids})
    if problem:
        raise option_error(problem)
    seller = gate.get("seller_profiles") or {}
    # Coming soon (or active without pickup coordinates): no menu to order from yet
    if with_buyer_status(dict(seller)).get("status") != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This store is not taking orders yet")
    if is_same_day(gate.get("preorder_day")) and not is_open_now(seller.get("is_open"), seller.get("weekly_hours"), seller_id=request.seller_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=STORE_CLOSED_DETAIL)
    # T134: today's portions of a same-day dish (a pre-order dish is checked for its delivery day at POST /orders)
    if gate.get("daily_portions") and is_same_day(gate.get("preorder_day")):
        cart_now = DAOCartItems().read_cart_items_by_user_id(user_id=user_id) or {}
        in_cart = sum(i["quantity"] for i in cart_now.get("cart_items") or []
                      if (i.get("food_items") or {}).get("id") == request.food_item_id)
        short = portions_error({request.food_item_id: in_cart + request.quantity}, {request.food_item_id: gate.get("name")},
                               datetime.datetime.now(VN_TZ).date())
        if short:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=short)

    dao_cart = DAOCarts()    
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user_id)
    if cart:
        cart_id = cart["id"]
        seller_id = cart["seller_id"]
        if not seller_id == request.seller_id:
            current_seller_name = cart.get("seller_profiles", {}).get("store_name", "")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Cart contains items from another seller",
                    "current_seller_name": current_seller_name
                }
            )
    else:
        new_cart = dao_cart.create_cart(user_id=user_id, seller_id=request.seller_id)
        if not new_cart:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create cart")
        cart_id = new_cart["id"]
        
    most, lines = max_per_dish(), max_lines()
    try:
        DAOCartItems().add_item(cart_id, request.food_item_id, request.variant_id, option_ids, request.quantity,
                                most, lines)
    except CartLimit as e:
        raise quantity_max_error(most) if str(e) == "quantity_max" else lines_max_error(lines)

    return {"success": True}


def _cart_line(user_id: str, item_id, food_item_id=None, variant_id=None):
    """(cart id, the caller's cart rows, the row asked for): by cart_items.id, or the old way (food_item_id +
    variant_id, from a page still running the JS before option groups) = that dish's row without options.
    404 when the caller's cart has no such row. TODO: drop the old way one release after option groups (QĐ3-3d)."""
    cart = DAOCarts().read_cart_by_user_id_seller_id(user_id=user_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    lines = DAOCartItems().read_lines(cart["id"])
    line = next((l for l in lines if l["id"] == str(item_id)), None) or \
        next((l for l in lines if l["food_item_id"] == str(food_item_id) and l["variant_id"] == variant_id
              and not l["option_ids"]), None)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This item is no longer in your cart")
    return cart["id"], lines, line


@router.patch("/update")
def update_food_item_quantity(request: Schema.RequestUpdateCartItem, user=Depends(verify_token)):

    check_quantities([request.quantity])
    cart_id, lines, line = _cart_line(user["id"], request.id, request.food_item_id, request.variant_id)
    # The cap is on the dish over all its rows (QĐ3-4b)
    check_quantities([request.quantity + sum(l["quantity"] for l in lines
                                             if l["food_item_id"] == line["food_item_id"] and l["id"] != line["id"])])
    DAOCartItems().update_quantity(cart_id, line["id"], request.quantity)

    return {"success": True}


@router.delete("/remove/{item_id}")
def remove_item_from_cart(item_id: uuid.UUID, variant_id: Optional[str] = None, user=Depends(verify_token)):
    """item_id = cart_items.id; the old JS sends the dish id here (+ variant_id): see _cart_line."""
    cart_id, _, line = _cart_line(user["id"], item_id, item_id, variant_id)
    DAOCartItems().remove_item(cart_id, line["id"])

    return {"success": True}


@router.delete("/clear")
def clear_cart(user=Depends(verify_token)):

    dao_cart = DAOCarts()
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user["id"])
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    dao_cart.delete_cart(cart_id=cart["id"])

    return {"success": True}
