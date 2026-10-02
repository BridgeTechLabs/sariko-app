import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


class DAOFoodItemVariants(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "food_item_variants"

    def read_by_food_item_id(self, food_item_id: str):
        result = (
            self._supabase_client.table(self._table_name)
            .select("id, is_available")
            .eq("food_item_id", food_item_id)
            .execute()
        )
        return result.data or []

    def read_parent_item_id(self, variant_id: str):
        """The dish a variant belongs to — the only way to check seller ownership,
        since food_item_variants carries no seller_id of its own."""
        result = (
            self._supabase_client.table(self._table_name)
            .select("food_item_id")
            .eq("id", variant_id)
            .limit(1)
            .execute()
        )
        return result.data[0]["food_item_id"] if result.data else None

    def create(self, food_item_id: str, fields: dict):
        fields["food_item_id"] = food_item_id
        result = (
            self._supabase_client.table(self._table_name)
            .insert(fields)
            .execute()
        )
        return result.data[0] if result.data else None

    def update(self, variant_id: str, fields: dict):
        result = (
            self._supabase_client.table(self._table_name)
            .update(fields)
            .eq("id", variant_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete(self, variant_id: str):
        try:
            result = (
                self._supabase_client.table(self._table_name)
                .delete()
                .eq("id", variant_id)
                .execute()
            )
            return result.data
        except PostgrestExceptionAPIError as e:
            # 23503 = cart_items_variant_id_fkey: the level is sitting in someone's
            # cart. The FK has no ON DELETE on purpose (see the table migration), so
            # this is expected, not a bug — the seller should hide it instead.
            if e.code == "23503":
                raise ValueError("variant_in_use")
            raise
