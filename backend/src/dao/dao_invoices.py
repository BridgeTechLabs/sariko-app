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

    def read_invoice_by_id(self, invoice_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("*") \
                .eq("id", invoice_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_invoice_by_id: {e}")
        except Exception as e:
            raise Exception(f"error read_invoice_by_id: {e}")

    def read_invoice_by_order_id(self, order_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("*") \
                .eq("order_id", order_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_invoice_by_order_id: {e}")
        except Exception as e:
            raise Exception(f"error read_invoice_by_order_id: {e}")

    def next_invoice_no(self) -> int:
        """Highest invoice_no + 1 (1 when there is none): request_id is built from it before the row exists."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("invoice_no") \
                .order("invoice_no", desc=True) \
                .limit(1) \
                .execute()

            return result.data[0]["invoice_no"] + 1 if result and result.data else 1

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - next_invoice_no: {e}")
        except Exception as e:
            raise Exception(f"error next_invoice_no: {e}")

    def update_pdf_path(self, invoice_id: str, pdf_path: str):
        result = self._supabase_client.table(self._table_name) \
            .update({"pdf_path": pdf_path}) \
            .eq("id", invoice_id) \
            .execute()

        return result.data[0] if result and result.data else None

    def create_invoice(self, data: dict):
        result = self._supabase_client.table(self._table_name) \
            .insert(data) \
            .execute()

        return result.data[0] if result and result.data else None
