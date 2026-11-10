import logging
from decimal import Decimal

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOAdminPayouts(DAOBase):
    """Read side of admin_payouts for the seller app; the admin repo writes them."""

    def __init__(self):
        super().__init__()
        self._table_name = "admin_payouts"

    def read_payouts_by_seller_id(self, seller_id: str, limit: int):
        """The seller's payout batches, newest first."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, period_start, period_end, order_count, net_payout, withholding_amount, total_deductions, status, paid_at") \
                .eq("seller_id", seller_id) \
                .neq("status", "cancelled") \
                .order("period_end", desc=True) \
                .limit(limit) \
                .execute()

            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_payouts_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_payouts_by_seller_id: {e}")

    def read_open_deductions(self, seller_id: str):
        """amount / applied_amount of the seller's deductions not fully taken yet (refunds charged to the seller,
        monthly fees): the next payout takes them (admin_generate_payout_for_seller step 7)."""
        try:
            result = self._supabase_client.table("admin_payout_deductions") \
                .select("amount, applied_amount") \
                .eq("seller_id", seller_id) \
                .execute()
            return [d for d in result.data or [] if Decimal(str(d["applied_amount"])) < Decimal(str(d["amount"]))]
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_open_deductions: {e}")

    def has_deduction_for_order(self, order_id: str) -> bool:
        """T176: a "Charge to seller" deduction exists for this order (the admin made it when cancelling)."""
        try:
            result = self._supabase_client.table("admin_payout_deductions").select("id").eq("order_id", order_id).limit(1).execute()
            return bool(result.data)
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - has_deduction_for_order: {e}")
