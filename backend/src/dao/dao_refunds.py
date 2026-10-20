import logging
from typing import Optional

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAORefunds(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "refunds"

    def create_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        original_txn_ref: Optional[str] = None,
        ipn_data: Optional[dict] = None,
        payment_create_date: Optional[str] = None,
    ):
        try:
            data = {
                "order_id": order_id,
                "amount": amount,
                "reason": reason,
                "status": "pending",
            }
            if original_txn_ref:
                data["original_txn_ref"] = original_txn_ref
            if ipn_data:
                data["ipn_data"] = ipn_data
            if payment_create_date:
                data["payment_create_date"] = payment_create_date

            result = self._supabase_client.table(self._table_name) \
                .insert(data) \
                .execute()

            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_refund: {e}")
        except Exception as e:
            raise Exception(f"error create_refund: {e}")

    def create_refund_for_order(self, order: dict, reason: str):
        """Queue a full refund for a cancelled order, if it was paid. The admin repo
        sends it to VNPay. Never raises, because the cancel has already happened;
        a second refund for the same order is refused by refunds_order_id_key."""
        if order.get("payment_status") != "paid":
            return None
        try:
            return self.create_refund(
                order_id=order["id"],
                amount=order["total_amount"],
                reason=reason,
                original_txn_ref=order.get("transaction_ref"),
                ipn_data=order.get("ipn_data"),
                payment_create_date=order.get("payment_create_date"),
            )
        except Exception as e:
            logger.error(f"Failed to create {reason} refund for order {order['id']}: {e}")
            return None
