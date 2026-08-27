import logging
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOFoodItems(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "food_items"

    def search_by_name(self, escaped_q: str, limit: int = 30):
        pattern = f"%{escaped_q}%"
        result = (
            self._supabase_client.table(self._table_name)
            .select(
                "id, name, image_url, preorder_day, "
                "menu_categories(name), "
                "seller_profiles(slug, store_name, avatar_url)"
            )
            .ilike("name", pattern)
            .eq("is_available", True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def read_featured_dishes(self, limit: int = 12):
        result = (
            self._supabase_client.table(self._table_name)
            .select("id, name, price_text, image_url, rating_avg, rating_count, seller_profiles!inner(id, slug, store_name)")
            .eq("is_featured", True)
            .eq("is_available", True)
            .eq("seller_profiles.is_listed", True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def read_food_items_by_seller_id(self, seller_id: str):
        result = (
            self._supabase_client.table("menu_categories")
            .select("id, name, food_items(id, name, price_text, price, description, image_url, rating_avg, rating_count, food_item_variants(id, name, price, price_text, sort_order, is_available))")
            .order("sort_order")
            .order("sort_order", foreign_table="food_items.food_item_variants")
            .eq("seller_id", seller_id)
            .execute()
        )
        return result.data or []

    def read_menu_by_seller_id(self, seller_id: str):
        result = (
            self._supabase_client.table("menu_categories")
            .select("id, name, sort_order, is_active, food_items(id, name, description, price, price_text, unit_label, min_quantity, quantity_step, preorder_day, is_available, is_featured, image_url, category_id, rating_avg, rating_count, food_item_variants(id, name, price, price_text, sort_order, is_available))")
            .eq("seller_id", seller_id)
            .order("sort_order")
            .order("sort_order", foreign_table="food_items.food_item_variants")
            .execute()
        )
        return result.data or []

    def create(self, seller_id: str, fields: dict):
        fields["seller_id"] = seller_id
        result = (
            self._supabase_client.table(self._table_name)
            .insert(fields)
            .execute()
        )
        return result.data[0] if result.data else None

    def update(self, item_id: str, seller_id: str, fields: dict):
        result = (
            self._supabase_client.table(self._table_name)
            .update(fields)
            .eq("id", item_id)
            .eq("seller_id", seller_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete(self, item_id: str, seller_id: str):
        result = (
            self._supabase_client.table(self._table_name)
            .delete()
            .eq("id", item_id)
            .eq("seller_id", seller_id)
            .execute()
        )
        return result.data
