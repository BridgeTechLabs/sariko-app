"""Admin Gateway: endpoints the admin backend (separate repo) calls with header X-Api-Key = ADMIN_GATEWAY_API_KEY
(T176, docs/dev/20261110-admin-cancel-notify). The key unset or empty turns the gateway off (503): an empty key never
matches. Not in the public /docs. The app trusts nothing but the key: it reads the order itself."""
import hmac
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from apis import sellers
from dao.dao_admin_payouts import DAOAdminPayouts
from dao.dao_orders import DAOOrders
from schemas import Schema
from services import push_service

logger = logging.getLogger(__name__)


def verify_gateway_key(x_api_key: str = Header(default="")):
    key = os.getenv("ADMIN_GATEWAY_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Admin Gateway is off")
    if not hmac.compare_digest(x_api_key.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


router = APIRouter(prefix="/admin-gateway", dependencies=[Depends(verify_gateway_key)], include_in_schema=False)


@router.post("/orders/{order_id}/cancelled-notify")
def cancelled_notify(order_id: UUID):
    """A4: an admin cancelled this order (admin repo apis/orders.py); push the buyer and, for a paid order, the seller
    like the app's own cancels do. Calling it twice pushes twice (QĐ B: accepted, rare)."""
    order_id = str(order_id)
    dao = DAOOrders()
    order = dao.read_order_by_id_raw(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] != "cancelled":
        raise HTTPException(status_code=409, detail="Order is not cancelled")
    was_done = any(h["status"] == "done" for h in dao.read_status_history(order_id))
    push_service.notify_admin_cancelled(
        order, was_done, charged=was_done and DAOAdminPayouts().has_deduction_for_order(order_id))
    logger.warning(f"[AdminGateway] cancel of order={order_id} pushed (paid={order['payment_status']}, done={was_done})")
    return {"success": True}


# ── Menu edits (T-admin-menu-edit, docs/dev/20261114-admin-menu-edit): an admin edits a store's option groups and
# a dish's fields (stock, minimum per order...) through the seller routes' own code, with the seller_id of the path:
# the same rules, limits and checks, and a dish / group of another store answers 404 like it does for that store's
# seller. The admin backend has its own admin login; here the key is all there is.

def _menu_edit(what: str, seller_id: UUID, edit, *args):
    result = edit(str(seller_id), *args)
    logger.info(f"admin edit seller={seller_id} {what}")
    return result


@router.patch("/sellers/{seller_id}/menu/items/{item_id}")
def edit_dish(seller_id: UUID, item_id: UUID, body: Schema.RequestUpdateFoodItem):
    return _menu_edit(f"dish={item_id} fields={sorted(body.model_fields_set)}", seller_id, sellers.update_food_item_for, str(item_id), body)


@router.post("/sellers/{seller_id}/menu/items/{item_id}/option-groups")
def create_option_group(seller_id: UUID, item_id: UUID, body: Schema.RequestOptionGroup):
    return _menu_edit(f"new option group on dish={item_id}", seller_id, sellers.create_option_group_for, str(item_id), body)


@router.put("/sellers/{seller_id}/menu/items/{item_id}/option-groups")
def order_option_groups(seller_id: UUID, item_id: UUID, body: Schema.RequestDishGroupOrder):
    return _menu_edit(f"option group order on dish={item_id}", seller_id, sellers.order_option_groups_for, str(item_id), body)


@router.post("/sellers/{seller_id}/menu/items/{item_id}/option-groups/{group_id}")
def attach_option_group(seller_id: UUID, item_id: UUID, group_id: UUID):
    return _menu_edit(f"attach group={group_id} to dish={item_id}", seller_id, sellers.attach_option_group_for, str(item_id), str(group_id))


@router.delete("/sellers/{seller_id}/menu/items/{item_id}/option-groups/{group_id}")
def detach_option_group(seller_id: UUID, item_id: UUID, group_id: UUID):
    return _menu_edit(f"detach group={group_id} from dish={item_id}", seller_id, sellers.detach_option_group_for, str(item_id), str(group_id))


@router.put("/sellers/{seller_id}/menu/option-groups/{group_id}")
def update_option_group(seller_id: UUID, group_id: UUID, body: Schema.RequestOptionGroup):
    return _menu_edit(f"option group={group_id}", seller_id, sellers.update_option_group_for, str(group_id), body)


@router.delete("/sellers/{seller_id}/menu/option-groups/{group_id}")
def delete_option_group(seller_id: UUID, group_id: UUID):
    return _menu_edit(f"delete option group={group_id}", seller_id, sellers.delete_option_group_for, str(group_id))
