from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase


class DAOInvoices(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "invoices"

    def read_invoice_by_request_id(self, request_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("*") \
                .eq("request_id", request_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_invoice_by_request_id: {e}")
        except Exception as e:
            raise Exception(f"error read_invoice_by_request_id: {e}")

    def create_invoice(self, data: dict):
        """Raises PostgrestExceptionAPIError as-is so callers can spot the request_id unique violation."""
        result = self._supabase_client.table(self._table_name) \
            .insert(data) \
            .execute()

        return result.data[0] if result and result.data else None

    def create_invoice_orders(self, invoice_id: str, order_ids: list[str]):
        """Raises PostgrestExceptionAPIError as-is: a unique violation means an order is already in an active invoice."""
        result = self._supabase_client.table("invoice_orders") \
            .insert([{"invoice_id": invoice_id, "order_id": order_id} for order_id in order_ids]) \
            .execute()

        return result.data if result and result.data else []

    def deactivate_invoice_orders(self, invoice_id: str):
        """Free the invoice's orders so they can be invoiced again."""
        try:
            self._supabase_client.table("invoice_orders") \
                .update({"active": False}) \
                .eq("invoice_id", invoice_id) \
                .execute()

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - deactivate_invoice_orders: {e}")
        except Exception as e:
            raise Exception(f"error deactivate_invoice_orders: {e}")

    def update_invoice(self, invoice_id: str, data: dict):
        try:
            result = self._supabase_client.table(self._table_name) \
                .update(data) \
                .eq("id", invoice_id) \
                .execute()

            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_invoice: {e}")
        except Exception as e:
            raise Exception(f"error update_invoice: {e}")
