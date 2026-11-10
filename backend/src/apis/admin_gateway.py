"""Admin Gateway: endpoints the admin backend (separate repo) calls with header X-Api-Key = ADMIN_GATEWAY_API_KEY
(T176, docs/dev/20261110-admin-cancel-notify). The key unset or empty turns the gateway off (503): an empty key never
matches. Not in the public /docs. The app trusts nothing but the key: it reads the order itself."""
import hmac
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from dao.dao_admin_payouts import DAOAdminPayouts
from dao.dao_orders import DAOOrders
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
