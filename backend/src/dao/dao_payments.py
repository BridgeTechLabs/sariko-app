import logging
from decimal import Decimal
from typing import Optional

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOPayments(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "payments"

    def create_payment(
        self,
        order_id: str,
        method: str,
        amount: Decimal,
        status: str,
        transaction_ref: str,
        type: str = "charge",
        vnp_transaction_no: Optional[str] = None,
        refund_id: Optional[str] = None,
    ):
        try:
            data = {
                "order_id": order_id,
                "method": method,
                "amount": str(amount),
                "status": status,
                "transaction_ref": transaction_ref,
                "type": type,
            }
            if vnp_transaction_no:
                data["vnp_transaction_no"] = vnp_transaction_no
            if refund_id:
                data["refund_id"] = refund_id

            result = self._supabase_client.table(self._table_name) \
                .insert(data) \
                .execute()

            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_payment: {e}")
        except Exception as e:
            raise Exception(f"error create_payment: {e}")

    def has_transaction(self, transaction_ref: str) -> bool:
        """A payment row already exists for this VNPay TxnRef (a result recorded once)."""
        try:
            result = self._supabase_client.table(self._table_name).select("id") \
                .eq("transaction_ref", transaction_ref).limit(1).execute()
            return bool(result.data)
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - has_transaction: {e}")
