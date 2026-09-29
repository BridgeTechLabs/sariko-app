import datetime
import uuid
import traceback
from typing import List, Optional
import json
import logging

from dao.dao_cart_items import DAOCartItems
from dao.dao_carts import DAOCarts
from dao.dao_food_item_variants import DAOFoodItemVariants
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
    _validate_variant(request.food_item_id, request.variant_id)

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
        
    dao_cart_items = DAOCartItems()
    existing_item = dao_cart_items.find_item(cart_id=cart_id, food_item_id=request.food_item_id, variant_id=request.variant_id)

    if existing_item:
        dao_cart_items.update_quantity(cart_id=cart_id, food_item_id=request.food_item_id, quantity=existing_item["quantity"] + request.quantity, variant_id=request.variant_id)
    else:
        dao_cart_items.update_food_item_by_cart_id(cart_id=cart_id, food_item_id=request.food_item_id, quantity=request.quantity, variant_id=request.variant_id)

    return {"success": True}

@router.patch("/update")
def update_food_item_quantity(request: Schema.RequestUpdateCartItem, user=Depends(verify_token)):

    dao_cart = DAOCarts()
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user["id"])
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    dao_cart_items = DAOCartItems()
    dao_cart_items.update_quantity(cart_id=cart["id"], food_item_id=request.food_item_id, quantity=request.quantity, variant_id=request.variant_id)

    return {"success": True}


@router.delete("/remove/{food_item_id}")
def remove_item_from_cart(food_item_id: str, variant_id: Optional[str] = None, user=Depends(verify_token)):

    dao_cart = DAOCarts()
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user["id"])
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    dao_cart_items = DAOCartItems()
    dao_cart_items.remove_item(cart_id=cart["id"], food_item_id=food_item_id, variant_id=variant_id)

    return {"success": True}


@router.delete("/clear")
def clear_cart(user=Depends(verify_token)):

    dao_cart = DAOCarts()
    cart = dao_cart.read_cart_by_user_id_seller_id(user_id=user["id"])
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    dao_cart.delete_cart(cart_id=cart["id"])

    return {"success": True}
