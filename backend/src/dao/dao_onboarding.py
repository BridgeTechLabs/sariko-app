import logging
from datetime import datetime, timezone

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

# Postgres invalid_text_representation: a malformed uuid in the URL.
PG_INVALID_TEXT = "22P02"


class DAOOnboarding(DAOBase):
    """Seller applications from the public /join form (onboarding_applications + onboarding_files)."""

    def __init__(self):
        super().__init__()

    def get_tier_limits(self, tier: str):
        """{max_items, max_categories} of a tier (null = unlimited), or None if the tier is unknown."""
        result = (
            self._supabase_client.table("admin_tier_config")
            .select("max_items, max_categories")
            .eq("tier", tier)
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    def list_tiers(self, tiers) -> list:
        """Rate, monthly fee (VND) and limits of the given plans."""
        result = (
            self._supabase_client.table("admin_tier_config")
            .select("tier, commission_rate, monthly_fee_vnd, max_items, max_categories")
            .in_("tier", list(tiers))
            .execute()
        )
        return result.data or []

    def create_application(self, data: dict) -> dict:
        result = self._supabase_client.table("onboarding_applications").insert(data).execute()
        return result.data[0]

    def get_application(self, application_id: str):
        try:
            result = (
                self._supabase_client.table("onboarding_applications")
                .select("id, status, created_at, upload_token, menu")
                .eq("id", application_id)
                .maybe_single()
                .execute()
            )
        except PostgrestExceptionAPIError as e:
            if e.code == PG_INVALID_TEXT:
                return None
            raise
        return result.data if result else None

    def list_files(self, application_id: str) -> list:
        result = (
            self._supabase_client.table("onboarding_files")
            .select("id, kind, item_key, storage_path")
            .eq("application_id", application_id)
            .execute()
        )
        return result.data or []

    def create_file(self, data: dict) -> dict:
        result = self._supabase_client.table("onboarding_files").insert(data).execute()
        return result.data[0]

    def delete_file(self, file_id: str) -> None:
        self._supabase_client.table("onboarding_files").delete().eq("id", file_id).execute()

    def submit(self, application_id: str) -> bool:
        """draft -> submitted. Conditional on status so a double submit updates nothing."""
        result = (
            self._supabase_client.table("onboarding_applications")
            .update({
                "status": "submitted",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "upload_token": None,
            })
            .eq("id", application_id)
            .eq("status", "draft")
            .execute()
        )
        return bool(result.data)
