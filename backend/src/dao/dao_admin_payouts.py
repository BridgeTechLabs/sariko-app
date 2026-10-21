import logging

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
                .order("period_end", desc=True) \
                .limit(limit) \
                .execute()

            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_payouts_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_payouts_by_seller_id: {e}")
