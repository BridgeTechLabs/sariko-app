import logging
from postgrest.exceptions import APIError as PostgrestExceptionAPIError
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOAdminConfig(DAOBase):

    def __init__(self):
        super().__init__()

    def get_tax_rate(self, key: str = "vat_rate") -> float:
        try:
            result = (
                self._supabase_client
                .table("admin_tax_config")
                .select("rate")
                .eq("key", key)
                .maybe_single()
                .execute()
            )
            if result and result.data:
                return float(result.data["rate"])
            raise Exception(f"Tax config key '{key}' not found")

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - get_tax_rate: {e}")
        except Exception as e:
            raise Exception(f"error get_tax_rate: {e}")

    def get_setting(self, key: str):
        """A platform setting from admin_settings (jsonb value), or None if the row is missing."""
        try:
            result = (
                self._supabase_client
                .table("admin_settings")
                .select("value")
                .eq("key", key)
                .maybe_single()
                .execute()
            )
            return result.data["value"] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - get_setting: {e}")
        except Exception as e:
            raise Exception(f"error get_setting: {e}")
