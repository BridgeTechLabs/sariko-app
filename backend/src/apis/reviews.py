import logging

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    status,
)

from core.auth import verify_token
from core.display_name import mask_display_name
from dao.dao_orders import DAOOrders
from dao.dao_reviews import DAOReviews, ReviewAlreadyExists
from schemas import Schema

router = APIRouter(prefix="/reviews")
logger = logging.getLogger(__name__)


def mask_reviewer(row: dict) -> None:
    """Replace the joined user record with a masked name + avatar, in place.

    Mutates the row rather than returning a copy — callers layer their own flattening
    on top of the same dict. Returning nothing keeps that contract unambiguous.
    """
    reviewer = row.pop("users", None) or {}
    row["reviewer_name"] = mask_display_name(reviewer.get("name"))
    row["reviewer_avatar_url"] = reviewer.get("avatar_url")


@router.post("")
def create_review(request: Schema.RequestCreateReview, user=Depends(verify_token)):

    user_id = user["id"]

    # Scoping the read by user_id makes this both the existence check and the
    # ownership check — a stranger's order id is simply "not found".
    dao_orders = DAOOrders()
    order = dao_orders.read_order_by_id(order_id=request.order_id, user_id=user_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["status"] != "done":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed orders can be reviewed")

    if order["payment_status"] != "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only paid orders can be reviewed")

    # A dish may only be rated by someone who actually ordered it; its name is the one on the order.
    ordered_names = {
        item["food_item_id"]: item["name_snapshot"] for item in (order.get("order_items") or [])
        if item.get("food_item_id")
    }
    for item in request.items:
        if item.food_item_id not in ordered_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot review a dish that is not part of this order",
            )

    seller_id = order["seller_id"]
    store_row = {
        "order_id": request.order_id,
        "seller_id": seller_id,
        "user_id": user_id,
        "rating": request.overall_rating,
        "comment": request.overall_comment,
    }
    item_rows = [{
        "order_id": request.order_id,
        "seller_id": seller_id,
        "user_id": user_id,
        "food_item_id": item.food_item_id,
        "name_snapshot": ordered_names[item.food_item_id],
        "rating": item.rating,
        "comment": item.comment,
    } for item in request.items]

    try:
        store, items = DAOReviews().create_review(store_row, item_rows)
    except ReviewAlreadyExists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already reviewed")

    return {"success": True, "store_review": store, "items": items}


@router.get("/orders/{order_id}")
def get_order_review(order_id: str, user=Depends(verify_token)):

    store, items = DAOReviews().read_order_review(order_id=order_id, user_id=user["id"])

    return {
        "success": True,
        "reviewed": store is not None,
        "overall_rating": store["rating"] if store else None,
        "overall_comment": store["comment"] if store else None,
        "items": items,   # a deleted dish: food_item_id None, name_snapshot kept
    }


@router.get("/food/{food_item_id}")
def get_food_item_reviews(
    food_item_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):

    dao_reviews = DAOReviews()
    reviews = dao_reviews.read_reviews_by_food_item_id(
        food_item_id=food_item_id, limit=limit, offset=offset
    )

    for review in reviews:
        mask_reviewer(review)

    return {"success": True, "reviews": reviews}
