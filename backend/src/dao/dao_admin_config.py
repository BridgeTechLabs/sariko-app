import logging
from datetime import timedelta
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

    def get_positive_int(self, key: str, default: int) -> int:
        """An integer > 0 setting. Read on every call, so an admin change applies at
        once. A missing or invalid value (0, "abc") falls back to the default rather
        than letting a typo cancel or unlock every order at once."""
        value = self.get_setting(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        logger.error(f"[Settings] invalid {key}={value!r}, using {default}")
        return default

    def get_minutes(self, key: str, default: int) -> timedelta:
        return timedelta(minutes=self.get_positive_int(key, default))
