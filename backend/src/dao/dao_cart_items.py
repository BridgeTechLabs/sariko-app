from typing import Optional
import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

class DAOCartItems(DAOBase):
    
    def __init__(self):
        super().__init__()
        self._table_name = "cart_items"
        
        
    def read_cart_items_by_user_id(self, user_id: str):
        
        try:
            result = self._supabase_client.table("carts") \
                .select("id, seller_id, seller_profiles(slug, store_name), cart_items(quantity, variant_id, food_items(id, name, price_text, price, unit_label, preorder_day, image_url, menu_categories(name)), food_item_variants(id, name, price, price_text))") \
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
        
        
        
    @staticmethod
    def _match_variant(query, variant_id: Optional[str]):
        """Narrow a cart_items query to one (dish, level) pair.

        variant_id None means "the dish has no levels" — which is NOT the same as
        "any level". The two partial unique indexes on cart_items keep those as
        separate rows, so an omitted filter would match the wrong row (or several).
        """
        if variant_id is None:
            return query.is_("variant_id", "null")
        return query.eq("variant_id", variant_id)


    def find_item(self, cart_id: str, food_item_id: str, variant_id: Optional[str] = None):

        try:
            query = self._supabase_client.table(self._table_name) \
                .select("id, quantity") \
                .eq("cart_id", cart_id) \
                .eq("food_item_id", food_item_id)
            result = self._match_variant(query, variant_id) \
                .limit(1) \
                .execute()

            if result and result.data:
                return result.data[0]

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - find_item with cart_id {cart_id} and food_item_id {food_item_id}: {e}")
        except Exception as e:
            raise Exception(f"error find_item with cart_id {cart_id} and food_item_id {food_item_id}: {e}")

    def update_quantity(self, cart_id: str, food_item_id: str, quantity: int, variant_id: Optional[str] = None):

        try:
            query = self._supabase_client.table(self._table_name) \
                .update({"quantity": quantity}) \
                .eq("cart_id", cart_id) \
                .eq("food_item_id", food_item_id)
            result = self._match_variant(query, variant_id).execute()

            if result and result.data:
                return result.data

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_quantity with cart_id {cart_id} and food_item_id {food_item_id}: {e}")

        except Exception as e:
            raise Exception(f"error update_quantity with cart_id {cart_id} and food_item_id {food_item_id}: {e}")


    def remove_item(self, cart_id: str, food_item_id: str, variant_id: Optional[str] = None):

        try:
            query = self._supabase_client.table(self._table_name) \
                .delete() \
                .eq("cart_id", cart_id) \
                .eq("food_item_id", food_item_id)
            result = self._match_variant(query, variant_id).execute()

            return True

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - remove_item with cart_id {cart_id} and food_item_id {food_item_id}: {e}")

        except Exception as e:
            raise Exception(f"error remove_item with cart_id {cart_id} and food_item_id {food_item_id}: {e}")


    def update_food_item_by_cart_id(self, cart_id: str, food_item_id: str, quantity: int = 1, variant_id: Optional[str] = None):

        try:

            query = self._supabase_client.table(self._table_name)
            query = query.insert({"cart_id": cart_id, "food_item_id": food_item_id, "variant_id": variant_id, "quantity": quantity})
    
            result = query.execute()
            
            if result and result.data:
                return result.data
            
            return None

        except PostgrestExceptionAPIError as e:
            # 23505 = cart_items_dish_variant_key / cart_items_dish_novariant_key:
            # a concurrent add already inserted this (cart, dish, level).
            if e.code == "23505":
                return None
            raise Exception(f"Supabase error - update_food_item_by_cart_id with cart_id {cart_id} and food_item_id {food_item_id}: {e}")
                
        except Exception as e:
            raise Exception(f"error update_food_item_by_cart_id with cart_id {cart_id} and food_item_id {food_item_id}: {e}")        