import logging
from postgrest.exceptions import APIError as PostgrestExceptionAPIError
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAODeliveries(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "deliveries"

    def create_delivery(self, order_id: str, provider: str, status: str,
                        user_id: str = None, seller_user_id: str = None,
                        lalamove_order_id: str = None, share_link: str = None, allingo_order_id: str = None,
                        trip_fee: int = None, allingo_partner: str = None):
        try:
            data = {
                "order_id": order_id,
                "provider": provider,
                "status": status,
            }
            if user_id:
                data["user_id"] = user_id
            if seller_user_id:
                data["seller_user_id"] = seller_user_id
            if lalamove_order_id:
                data["lalamove_order_id"] = lalamove_order_id
            if allingo_order_id:
                data["allingo_order_id"] = allingo_order_id
            if share_link:
                data["share_link"] = share_link
            if allingo_partner:
                data["allingo_partner"] = allingo_partner   # T192: which company AllinGo booked
            if trip_fee is not None:
                data["trip_fee"] = trip_fee   # T180 A12: what the company charges for this trip

            result = (
                self._supabase_client
                .table(self._table_name)
                .insert(data)
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_delivery: {e}")
        except Exception as e:
            raise Exception(f"error create_delivery: {e}")

    def read_delivery_by_order_id(self, order_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("*")
                .eq("order_id", order_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_delivery_by_order_id: {e}")
        except Exception as e:
            raise Exception(f"error read_delivery_by_order_id: {e}")

    def read_delivery_by_lalamove_order_id(self, lalamove_order_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("*")
                .eq("lalamove_order_id", lalamove_order_id)
                .maybe_single()
                .execute()
            )
            return result.data if result else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_delivery_by_lalamove_order_id: {e}")
        except Exception as e:
            raise Exception(f"error read_delivery_by_lalamove_order_id: {e}")

    def read_delivery_by_allingo_order_id(self, allingo_order_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("*")
                .eq("allingo_order_id", allingo_order_id)
                .maybe_single()
                .execute()
            )
            return result.data if result else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_delivery_by_allingo_order_id: {e}")
        except Exception as e:
            raise Exception(f"error read_delivery_by_allingo_order_id: {e}")

    def update_delivery(self, delivery_id: str, data: dict):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .update(data)
                .eq("id", delivery_id)
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_delivery: {e}")
        except Exception as e:
            raise Exception(f"error update_delivery: {e}")
