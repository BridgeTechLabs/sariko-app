import uuid
import traceback
from typing import List, Optional
import json
import logging

from dao.dao_cart_items import CartGone, CartLimit, DAOCartItems
from dao.dao_carts import DAOCarts
from dao.dao_food_item_variants import DAOFoodItemVariants
from dao.dao_food_items import DAOFoodItems
from apis.orders import (STORE_CLOSED_DETAIL, check_quantities, is_same_day, lines_max_error, max_lines,
                         max_per_dish, option_error, option_problem, quantity_max_error)
from core.store_hours import is_open_now
from core.seller_status import with_buyer_status
from utils.pricing import cart_item_unit_price, options_snapshot
from utils.stock import add_sold_out, stock_error, stock_sold_out
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
    if cart:   # stock + min_quantity + sold_out: the cart shows a dish short of stock or under its minimum (QĐ2-12)
        add_sold_out([ci["food_items"] for ci in cart["cart_items"]])
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
    # Off sale ("Đang bán" off), or fewer left than one order takes (QĐ2-7): shown as Sold out in the menu
    if gate.get("is_available") is False or stock_sold_out(gate):
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
    # The dish's stock against all its rows in the cart, same-day and pre-order alike (QĐ2-8 a)
    if gate.get("stock") is not None:
        cart_now = DAOCartItems().read_cart_items_by_user_id(user_id=user_id) or {}
        in_cart = sum(i["quantity"] for i in cart_now.get("cart_items") or []
                      if (i.get("food_items") or {}).get("id") == request.food_item_id)
        short = stock_error({request.food_item_id: in_cart + request.quantity}, {request.food_item_id: gate})
        if short:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=short)

    def add():
        cart_id = _cart_id(user_id, request.seller_id)   # the store rule first, as before
        most, lines = max_per_dish(), max_lines()
        try:
            DAOCartItems().add_item(cart_id, request.food_item_id, request.variant_id, option_ids, request.quantity,
                                    most, lines)
        except CartLimit as e:
            raise quantity_max_error(most) if str(e) == "quantity_max" else lines_max_error(lines)

    try:
        add()
    except CartGone:
        # T210: the cart went between the read and the add (the same buyer cleared it or placed the order in another
        # tab): nothing was written, so the cart is read / made again and the add tried once more, as a second tap
        # would. Its store rule holds (_cart_id); failing again is an error as before.
        add()
    return {"success": True}


def _cart_id(user_id: str, seller_id: str) -> str:
    """The buyer's cart for this store, made when there is none; 400 when the cart holds another store's dishes."""
    dao_cart = DAOCarts()
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user_id)
    if cart:
        if not cart["seller_id"] == seller_id:
            current_seller_name = cart.get("seller_profiles", {}).get("store_name", "")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Cart contains items from another seller",
                    "current_seller_name": current_seller_name
                }
            )
        return cart["id"]
    new_cart = dao_cart.create_cart(user_id=user_id, seller_id=seller_id)
    if not new_cart:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create cart")
    return new_cart["id"]


def _cart_line(user_id: str, item_id):
    """(cart id, the caller's cart rows, the row asked for): by cart_items.id; 404 when the caller's cart has no such row."""
    cart = DAOCarts().read_cart_by_user_id_seller_id(user_id=user_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    lines = DAOCartItems().read_lines(cart["id"])
    line = next((l for l in lines if l["id"] == str(item_id)), None)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This item is no longer in your cart")
    return cart["id"], lines, line


@router.patch("/update")
def update_food_item_quantity(request: Schema.RequestUpdateCartItem, user=Depends(verify_token)):

    check_quantities([request.quantity])
    cart_id, lines, line = _cart_line(user["id"], request.id)
    # The cap is on the dish over all its rows (QĐ3-4b)
    check_quantities([request.quantity + sum(l["quantity"] for l in lines
                                             if l["food_item_id"] == line["food_item_id"] and l["id"] != line["id"])])
    DAOCartItems().update_quantity(cart_id, line["id"], request.quantity)

    return {"success": True}


@router.delete("/remove/{item_id}")
def remove_item_from_cart(item_id: uuid.UUID, user=Depends(verify_token)):
    """item_id = cart_items.id"""
    cart_id, _, line = _cart_line(user["id"], item_id)
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
