from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

PG_UNIQUE_VIOLATION = "23505"   # complaints_one_open_uidx: one unresolved complaint per order and sender

# What a buyer or seller may see of a complaint: never admin_note, held_payout or the storage paths.
PUBLIC_FIELDS = ("id, code, order_id, user_id, sender_role, channel, category, description, image_paths, status, "
                 "resolution, created_at, acknowledged_at, resolved_at")


class ComplaintOpenExists(Exception):
    """The sender already has an unresolved complaint on this order."""


class DAOComplaints(DAOBase):
    """complaints (T35, migration 20261021090000). Backend only: the table has no client grants."""

    def read_order(self, order_id: str):
        """The order fields the complaint rules need, with the seller's user id."""
        try:
            result = self._supabase_client.table("orders") \
                .select("id, user_id, seller_id, status, payment_status, status_changed_at, seller_profiles(user_id, store_name)") \
                .eq("id", order_id).maybe_single().execute()
            return result.data if result and result.data else None
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - complaints read_order: {e}")

    def create(self, order_id: str, user_id: str, sender_role: str, category: str, description: str) -> dict:
        """create_complaint RPC: the row and, for a buyer, the payout hold in one transaction."""
        try:
            return self._supabase_client.rpc("create_complaint", {
                "p_order_id": order_id, "p_user_id": user_id, "p_sender_role": sender_role,
                "p_channel": "app", "p_category": category, "p_description": description,
            }).execute().data
        except PostgrestExceptionAPIError as e:
            if e.code == PG_UNIQUE_VIOLATION:
                raise ComplaintOpenExists()
            raise Exception(f"Supabase error - create_complaint: {e}")

    def read(self, complaint_id: str):
        try:
            result = self._supabase_client.table("complaints").select(PUBLIC_FIELDS) \
                .eq("id", complaint_id).maybe_single().execute()
            return result.data if result and result.data else None
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read complaint: {e}")

    def set_image_paths(self, complaint_id: str, paths: list):
        try:
            self._supabase_client.table("complaints").update({"image_paths": paths}) \
                .eq("id", complaint_id).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - set complaint images: {e}")

    def list_by_user(self, user_id: str):
        try:
            return self._supabase_client.table("complaints").select(PUBLIC_FIELDS) \
                .eq("user_id", user_id).order("created_at", desc=True).execute().data or []
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - list complaints: {e}")

    def list_for_order(self, order_id: str):
        try:
            return self._supabase_client.table("complaints").select(PUBLIC_FIELDS) \
                .eq("order_id", order_id).order("created_at", desc=True).execute().data or []
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - list order complaints: {e}")
