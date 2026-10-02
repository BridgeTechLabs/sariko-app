import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase
from utils.pricing import cart_item_unit_price

logger = logging.getLogger(__name__)


class DAOOrderItems(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "order_items"

    def create_order_items_from_cart(self, order_id: str, cart_items: list):
        try:
            rows = []
            for item in cart_items:
                food = item.get("food_items", {})
                variant = item.get("food_item_variants")
                rows.append({
                    "order_id": order_id,
                    "food_item_id": food.get("id"),
                    "name_snapshot": food.get("name"),
                    "price_snapshot": cart_item_unit_price(item),
                    "unit_label_snapshot": food.get("unit_label"),
                    "variant_name_snapshot": variant["name"] if variant else None,
                    "quantity": item.get("quantity"),
                })

            result = self._supabase_client.table(self._table_name) \
                .insert(rows) \
                .execute()

            if result and result.data:
                return result.data

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_order_items_from_cart: {e}")
        except Exception as e:
            raise Exception(f"error create_order_items_from_cart: {e}")
