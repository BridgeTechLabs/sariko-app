import logging
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOMenuCategories(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "menu_categories"

    def search_by_name(self, escaped_q: str, limit: int = 20):
        pattern = f"%{escaped_q}%"
        result = (
            self._supabase_client.table(self._table_name)
            .select("id, name, seller_profiles(slug, store_name, avatar_url)")
            .ilike("name", pattern)
            .eq("is_active", True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def read_by_seller_id(self, seller_id: str):
        result = (
            self._supabase_client.table(self._table_name)
            .select("*")
            .eq("seller_id", seller_id)
            .order("sort_order")
            .execute()
        )
        return result.data or []

    def is_owned_by_seller(self, category_id: str, seller_id: str) -> bool:
        result = (
            self._supabase_client.table(self._table_name)
            .select("id")
            .eq("id", category_id)
            .eq("seller_id", seller_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)

    def create(self, seller_id: str, name: str, sort_order: int = 0):
        result = (
            self._supabase_client.table(self._table_name)
            .insert({"seller_id": seller_id, "name": name, "sort_order": sort_order})
            .execute()
        )
        return result.data[0] if result.data else None

    def update(self, category_id: str, seller_id: str, fields: dict):
        result = (
            self._supabase_client.table(self._table_name)
            .update(fields)
            .eq("id", category_id)
            .eq("seller_id", seller_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete(self, category_id: str, seller_id: str):
        result = (
            self._supabase_client.table(self._table_name)
            .delete()
            .eq("id", category_id)
            .eq("seller_id", seller_id)
            .execute()
        )
        return result.data
