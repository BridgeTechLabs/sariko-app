import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

class DAOPushSubscriptions(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "push_subscriptions"

    def upsert_subscription(self, user_id: str, endpoint: str, p256dh: str, auth: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .upsert(
                    {"user_id": user_id, "endpoint": endpoint, "p256dh": p256dh, "auth": auth},
                    on_conflict="endpoint",
                )
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - upsert_subscription: {e}")
        except Exception as e:
            raise Exception(f"error upsert_subscription: {e}")

    def read_subscriptions_by_user_id(self, user_id: str):
        """Marketplace devices only: the same person's admin-panel subscription is not theirs to get."""
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("endpoint, p256dh, auth")
                .eq("user_id", user_id)
                .eq("app", "marketplace")
                .execute()
            )
            return result.data if result and result.data else []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_subscriptions_by_user_id: {e}")
        except Exception as e:
            raise Exception(f"error read_subscriptions_by_user_id: {e}")

    def read_admin_subscriptions(self):
        """Every admin-panel device (no admin roles: all admins get every admin push)."""
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("user_id, endpoint, p256dh, auth")
                .eq("app", "admin")
                .execute()
            )
            return result.data if result and result.data else []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_admin_subscriptions: {e}")
        except Exception as e:
            raise Exception(f"error read_admin_subscriptions: {e}")

    def delete_subscription(self, endpoint: str):
        try:
            self._supabase_client.table(self._table_name).delete().eq("endpoint", endpoint).execute()

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - delete_subscription: {e}")
        except Exception as e:
            raise Exception(f"error delete_subscription: {e}")
