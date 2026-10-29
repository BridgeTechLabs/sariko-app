from typing import Optional

from dao.dao_base import DAOBase

SELLER_FIELDS = "id, user_id, store_name, tier, phone, address, lat, lon, bank_name, bank_account_number, bank_account_holder"
APP_FIELDS = (
    "id, status, source, created_at, full_name, date_of_birth, nationality, id_type, id_number, "
    "id_expiry_date, email, residential_address, tax_code, tax_resident, agreement_version, "
    "personal_data_consent_at, signature_name"
)


class DAOSellerProfileCompletion(DAOBase):
    """Existing seller's profile (spec docs/dev/seller-profile-completion): operational fields
    in seller_profiles, identity / tax / agreement in onboarding_applications."""

    def read_seller(self, user_id: str) -> Optional[dict]:
        result = (
            self._supabase_client.table("seller_profiles")
            .select(SELLER_FIELDS).eq("user_id", user_id).maybe_single().execute()
        )
        return result.data if result and result.data else None

    def read_user_email(self, user_id: str) -> Optional[str]:
        result = self._supabase_client.table("users").select("email").eq("id", user_id).maybe_single().execute()
        return result.data.get("email") if result and result.data else None

    def read_application(self, seller_id: str) -> Optional[dict]:
        """The seller's KYC row: the in-app one if any, else the latest /join one the admin linked."""
        rows = (
            self._supabase_client.table("onboarding_applications")
            .select(APP_FIELDS).eq("seller_profile_id", seller_id)
            .order("created_at", desc=True).execute()
        ).data or []
        return next((r for r in rows if r["source"] == "existing_seller"), rows[0] if rows else None)

    def count_id_documents(self, application_id: str) -> int:
        rows = (
            self._supabase_client.table("onboarding_files")
            .select("id").eq("application_id", application_id).eq("kind", "id_document").execute()
        ).data or []
        return len(rows)

    def create_application(self, data: dict) -> dict:
        return self._supabase_client.table("onboarding_applications").insert(data).execute().data[0]

    def update_application(self, application_id: str, data: dict) -> None:
        self._supabase_client.table("onboarding_applications").update(data).eq("id", application_id).execute()

    def update_seller(self, seller_id: str, data: dict) -> None:
        self._supabase_client.table("seller_profiles").update(data).eq("id", seller_id).execute()

    def create_file(self, data: dict) -> dict:
        return self._supabase_client.table("onboarding_files").insert(data).execute().data[0]
