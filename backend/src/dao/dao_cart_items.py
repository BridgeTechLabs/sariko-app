import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase
from utils.pricing import OPTION_GROUPS_EMBED

logger = logging.getLogger(__name__)


class CartLimit(Exception):
    """add_cart_item refused the add: str(self) is "quantity_max" or "cart_max_lines"."""


class DAOCartItems(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "cart_items"


    def read_cart_items_by_user_id(self, user_id: str):

        try:
            result = self._supabase_client.table("carts") \
                .select("id, seller_id, seller_profiles(slug, store_name), cart_items(id, quantity, variant_id, option_ids, food_items(id, seller_id, name, price_text, price, unit_label, preorder_day, stock, min_quantity, image_url, is_available, menu_categories(name), " + OPTION_GROUPS_EMBED + "), food_item_variants(id, name, price, price_text, is_available))") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()

            if result and result.data:
                return result.data[0]

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_cart_items with user_id {user_id}: {e}")

        except Exception as e:
            raise Exception(f"error read_cart_items with user_id {user_id}: {e}")


    def add_item(self, cart_id: str, food_item_id: str, variant_id, option_ids: list, quantity: int,
                 max_quantity: int, max_lines: int):
        """One statement (rpc add_cart_item): a new row, or the quantity added to the row with the same dish,
        level and options. CartLimit when the dish total or the number of rows would pass its cap."""
        try:
            self._supabase_client.rpc("add_cart_item", {
                "p_cart_id": cart_id, "p_food_item_id": food_item_id, "p_variant_id": variant_id,
                "p_option_ids": option_ids, "p_qty": quantity, "p_max_qty": max_quantity, "p_max_lines": max_lines,
            }).execute()
        except PostgrestExceptionAPIError as e:
            if e.message in ("quantity_max", "cart_max_lines"):
                raise CartLimit(e.message)
            raise Exception(f"Supabase error - add_item with cart_id {cart_id} and food_item_id {food_item_id}: {e}")


    def read_lines(self, cart_id: str) -> list:
        return self._supabase_client.table(self._table_name) \
            .select("id, food_item_id, variant_id, option_ids, quantity") \
            .eq("cart_id", cart_id) \
            .execute().data or []


    # Both writes name the caller's cart in the statement itself: a row of another cart is never touched (BM8).
    def update_quantity(self, cart_id: str, item_id: str, quantity: int) -> list:
        return self._supabase_client.table(self._table_name) \
            .update({"quantity": quantity}) \
            .eq("id", item_id) \
            .eq("cart_id", cart_id) \
            .execute().data or []


    def remove_item(self, cart_id: str, item_id: str) -> list:
        return self._supabase_client.table(self._table_name) \
            .delete() \
            .eq("id", item_id) \
            .eq("cart_id", cart_id) \
            .execute().data or []
