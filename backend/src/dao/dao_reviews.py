import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

# Postgres unique_violation. Raised by review_stores_order_id_key / review_items_order_food_key
# when the same order is reviewed twice — the API turns this into a 409.
PG_UNIQUE_VIOLATION = "23505"


class ReviewAlreadyExists(Exception):
    """The order (or one of its dishes) has already been reviewed."""


class DAOReviews(DAOBase):
    """Two tables: review_stores (the store rating, one per order) and review_items
    (optional dish ratings; food_item_id is NULL once the dish is deleted, name_snapshot stays)."""

    def create_review(self, store_row: dict, item_rows: list):
        """Store row first (its unique order_id is the double-submit guard), then the dish rows.
        Two requests, so a failed second insert removes the first: all or nothing."""
        try:
            store = self._supabase_client.table("review_stores").insert(store_row).execute().data[0]
        except PostgrestExceptionAPIError as e:
            if e.code == PG_UNIQUE_VIOLATION:
                raise ReviewAlreadyExists()
            raise Exception(f"Supabase error - create_review: {e}")

        if not item_rows:
            return store, []
        try:
            items = self._supabase_client.table("review_items").insert(item_rows).execute().data
        except Exception as e:
            self._supabase_client.table("review_stores").delete().eq("id", store["id"]).execute()
            if isinstance(e, PostgrestExceptionAPIError) and e.code == PG_UNIQUE_VIOLATION:
                raise ReviewAlreadyExists()
            raise Exception(f"error create_review items: {e}")
        return store, items

    def read_order_review(self, order_id: str, user_id: str):
        """The buyer's own review of one order: (store row or None, dish rows)."""
        try:
            store = self._supabase_client.table("review_stores") \
                .select("id, rating, comment, created_at") \
                .eq("order_id", order_id) \
                .eq("user_id", user_id) \
                .execute().data
            items = self._supabase_client.table("review_items") \
                .select("id, food_item_id, name_snapshot, rating, comment, created_at") \
                .eq("order_id", order_id) \
                .eq("user_id", user_id) \
                .execute().data

            return (store[0] if store else None), (items or [])

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_review: {e}")
        except Exception as e:
            raise Exception(f"error read_order_review: {e}")

    def read_reviews_by_food_item_id(self, food_item_id: str, limit: int = 20, offset: int = 0):
        """Public list for a dish. Comment-less rows are returned too — a bare 5★ still counts."""
        try:
            result = self._supabase_client.table("review_items") \
                .select("id, rating, comment, created_at, users(name, avatar_url)") \
                .eq("food_item_id", food_item_id) \
                .order("created_at", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()

            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_reviews_by_food_item_id: {e}")
        except Exception as e:
            raise Exception(f"error read_reviews_by_food_item_id: {e}")

    def read_reviews_by_seller_id(self, seller_id: str, limit: int = 20, offset: int = 0):
        """Seller dashboard: a page of store reviews, each with the dish reviews of its order."""
        try:
            stores = self._supabase_client.table("review_stores") \
                .select("id, order_id, rating, comment, created_at, users(name, avatar_url)") \
                .eq("seller_id", seller_id) \
                .order("created_at", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute().data or []
            if not stores:
                return []

            items = self._supabase_client.table("review_items") \
                .select("id, order_id, food_item_id, name_snapshot, rating, comment") \
                .in_("order_id", [s["order_id"] for s in stores]) \
                .execute().data or []
            for store in stores:
                store["items"] = [i for i in items if i["order_id"] == store["order_id"]]

            return stores

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_reviews_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_reviews_by_seller_id: {e}")
