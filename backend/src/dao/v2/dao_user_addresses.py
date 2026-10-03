import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

SELECT_FIELDS = "id, label, address, lat, lon, is_default, receiver_name, phone_number, note, street_name, created_at, updated_at"


class DAOUserAddresses(DAOBase):
    """Every query is scoped by user_id, so a stranger's address id is simply not found."""

    def __init__(self):
        super().__init__()
        self._table_name = "user_addresses"

    def read_addresses(self, user_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select(SELECT_FIELDS)
                .eq("user_id", user_id)
                .order("is_default", desc=True)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_addresses: {e}")
        except Exception as e:
            raise Exception(f"error read_addresses: {e}")

    def read_address(self, user_id: str, address_id: int):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select(SELECT_FIELDS)
                .eq("user_id", user_id)
                .eq("id", address_id)
                .maybe_single()
                .execute()
            )
            return result.data if result else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_address: {e}")
        except Exception as e:
            raise Exception(f"error read_address: {e}")

    def has_address(self, user_id: str) -> bool:
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("id")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            return bool(result.data)

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - has_address: {e}")
        except Exception as e:
            raise Exception(f"error has_address: {e}")

    def clear_default(self, user_id: str, except_id: int = None):
        try:
            query = (
                self._supabase_client
                .table(self._table_name)
                .update({"is_default": False})
                .eq("user_id", user_id)
                .eq("is_default", True)
            )
            if except_id is not None:
                query = query.neq("id", except_id)
            query.execute()

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - clear_default: {e}")
        except Exception as e:
            raise Exception(f"error clear_default: {e}")

    def create_address(self, user_id: str, data: dict):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .insert({**data, "user_id": user_id})
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_address: {e}")
        except Exception as e:
            raise Exception(f"error create_address: {e}")

    def update_address(self, user_id: str, address_id: int, data: dict):
        # updated_at is stamped by the on_user_addresses_update trigger.
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .update(data)
                .eq("user_id", user_id)
                .eq("id", address_id)
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_address: {e}")
        except Exception as e:
            raise Exception(f"error update_address: {e}")
