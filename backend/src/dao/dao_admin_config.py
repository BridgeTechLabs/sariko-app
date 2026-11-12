import logging
from datetime import timedelta
from decimal import Decimal
from postgrest.exceptions import APIError as PostgrestExceptionAPIError
from core.sariko_cache import cache
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

SETTING_TTL_SECONDS = 60   # technical constant, not a business parameter: how long a read setting is kept
_MISSING = object()        # "not cached", apart from a cached None (a missing row)


def _cache_key(key: str) -> str:
    return f"admin_settings_{key}_value"


class DAOAdminConfig(DAOBase):

    def __init__(self):
        super().__init__()

    def get_tax_rate(self, key: str = "vat_rate") -> Decimal:
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
                return Decimal(str(result.data["rate"]))
            raise Exception(f"Tax config key '{key}' not found")

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - get_tax_rate: {e}")
        except Exception as e:
            raise Exception(f"error get_tax_rate: {e}")

    def get_setting(self, key: str):
        """A platform setting from admin_settings (jsonb value), or None if the row is missing. Cached 60 s,
        a missing row too; a failed read is not cached."""
        cached = cache.get(_cache_key(key), _MISSING)
        if cached is not _MISSING:
            return cached
        try:
            result = (
                self._supabase_client
                .table("admin_settings")
                .select("value")
                .eq("key", key)
                .maybe_single()
                .execute()
            )
            value = result.data["value"] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - get_setting: {e}")
        except Exception as e:
            raise Exception(f"error get_setting: {e}")
        cache.put(_cache_key(key), value, SETTING_TTL_SECONDS)
        return value

    def get_positive_int(self, key: str, default: int) -> int:
        """An integer > 0 setting. Cached 60 s: an admin change applies within a minute. A missing or invalid
        value (0, "abc") falls back to the default rather than letting a typo cancel or unlock every order at once."""
        return self._positive_int(key, self.get_setting(key), default)

    def get_positive_ints(self, defaults: dict) -> dict:
        """Several get_positive_int settings in one query (only the keys not cached): {key: value}, defaults for
        missing/invalid rows."""
        values = {k: v for k in defaults if (v := cache.get(_cache_key(k), _MISSING)) is not _MISSING}
        todo = [k for k in defaults if k not in values]
        if todo:
            try:
                result = (
                    self._supabase_client
                    .table("admin_settings")
                    .select("key, value")
                    .in_("key", todo)
                    .execute()
                )
            except PostgrestExceptionAPIError as e:
                raise Exception(f"Supabase error - get_positive_ints: {e}")
            rows = {row["key"]: row["value"] for row in (result.data or [])}
            for k in todo:
                values[k] = rows.get(k)
                cache.put(_cache_key(k), values[k], SETTING_TTL_SECONDS)
        return {key: self._positive_int(key, values[key], default) for key, default in defaults.items()}

    @staticmethod
    def _positive_int(key: str, value, default: int) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        logger.error(f"[Settings] invalid {key}={value!r}, using {default}")
        return default

    def get_int_in_range(self, key: str, default: int, lo: int, hi: int) -> int:
        """An integer setting that may be 0 (e.g. payout_generate_hour 0..23). Missing or
        out of range falls back to the default, like get_positive_int."""
        value = self.get_setting(key)
        if isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi:
            return value
        logger.error(f"[Settings] invalid {key}={value!r} (integer {lo}..{hi}), using {default}")
        return default

    def get_minutes(self, key: str, default: int) -> timedelta:
        return timedelta(minutes=self.get_positive_int(key, default))
