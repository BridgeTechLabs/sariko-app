"""
DEV-ONLY endpoints — hacker mode shortcuts for testing.
Remove this entire file (and its router in main.py) before production deployment.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends

from core.auth import verify_token
from dao.dao_orders import DAOOrders

router = APIRouter(prefix="/dev")
logger = logging.getLogger(__name__)


@router.patch("/orders/{order_id}/force-pay")
def force_pay(order_id: str, user=Depends(verify_token)):
    """Force-set payment_status to 'paid'."""
    dao_orders = DAOOrders()
    dao_orders.update_payment_status(order_id, "paid")
    logger.warning(f"[DEV] force-pay order {order_id} by user {user['id']}")
    return {"success": True}


@router.patch("/orders/{order_id}/force-unpay")
def force_unpay(order_id: str, user=Depends(verify_token)):
    """Force-set payment_status back to 'pending' (unpaid)."""
    dao_orders = DAOOrders()
    dao_orders.update_payment_status(order_id, "pending")
    logger.warning(f"[DEV] force-unpay order {order_id} by user {user['id']}")
    return {"success": True}


@router.patch("/orders/{order_id}/force-status")
def force_status(order_id: str, body: dict, user=Depends(verify_token)):
    """Force-set order status to any value."""
    new_status = body.get("status")
    if new_status not in ("pending", "confirmed", "ready", "done", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")
    dao_orders = DAOOrders()
    dao_orders.update_order_status(order_id, new_status)
    logger.warning(f"[DEV] force-status order {order_id} → {new_status} by user {user['id']}")
    return {"success": True}
