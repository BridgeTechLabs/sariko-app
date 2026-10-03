from typing import Optional
import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

class DAOUserAddresses(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "user_addresses"

    def read_default_address(self, user_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("id, label, address, lat, lon, is_default, receiver_name, phone_number, note, updated_at")
                .eq("user_id", user_id)
                .eq("is_default", True)
                .maybe_single()
                .execute()
            )
            return result.data if result else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_default_address: {e}")
        except Exception as e:
            raise Exception(f"error read_default_address: {e}")

    def upsert_default_address(self, user_id: str, address: str, address_details: str = None, lat: float = None, lon: float = None,
                               receiver_name: str = None, phone_number: str = None, note: str = None):
        try:
            existing = (
                self._supabase_client
                .table(self._table_name)
                .select("id")
                .eq("user_id", user_id)
                .eq("is_default", True)
                .maybe_single()
                .execute()
            )

            data = {
                "user_id": user_id,
                "label": address_details or "Home",
                "address": address,
                "lat": lat,
                "lon": lon,
                "is_default": True,
            }
            # Only send receiver fields the caller provided, so an address-only
            # update doesn't wipe them. updated_at is set by trigger.
            for field, value in (("receiver_name", receiver_name), ("phone_number", phone_number), ("note", note)):
                if value is not None:
                    data[field] = value

            if existing and existing.data:
                result = (
                    self._supabase_client
                    .table(self._table_name)
                    .update(data)
                    .eq("id", existing.data["id"])
                    .execute()
                )
            else:
                result = (
                    self._supabase_client
                    .table(self._table_name)
                    .insert(data)
                    .execute()
                )

            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - upsert_default_address: {e}")
        except Exception as e:
            raise Exception(f"error upsert_default_address: {e}")
