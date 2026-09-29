import logging
from typing import Optional

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from core.sariko_cache import cache
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)


def seller_orders_key(seller_id: str) -> str:
    """Cache key for a seller's order-list signature ({latest, count}).

    Lives here because this module owns the query the signature describes, and
    is imported by the /head route so the format is written down once.
    """
    return f"seller_{seller_id}_orders"


def _invalidate_seller_orders(seller_id: Optional[str]) -> None:
    """Drop a seller's cached signature so the next probe re-reads the database.

    Tolerates None so callers can pass a column straight off an updated row
    without a guard — an order with no seller_id has no cache entry anyway.
    """
    if seller_id:
        cache.invalidate(seller_orders_key(seller_id))


class DAOOrders(DAOBase):

    def __init__(self):
        super().__init__()
        self._table_name = "orders"

    def create_order(self, user_id: str, seller_id: str, seller_user_id: str,
        subtotal: float, total_amount: float,
        commission_rate: float, commission_amount: float,
        vat_rate: float, vat_amount: float,
        payout_amount: float,
        delivery_method: str, delivery_address: Optional[str] = None, note: Optional[str] = None,
        delivery_lat: Optional[float] = None, delivery_lon: Optional[float] = None,
        delivery_fee: Optional[float] = None, quotation_id: Optional[str] = None,
        delivery_appointment=None
    ):
        try:
            data = {
                "user_id": user_id,
                "seller_id": seller_id,
                "seller_user_id": seller_user_id,
                "subtotal": subtotal,
                "total_amount": total_amount,
                "commission_rate": commission_rate,
                "commission_amount": commission_amount,
                "vat_rate": vat_rate,
                "vat_amount": vat_amount,
                "payout_amount": payout_amount,
                "delivery_method": delivery_method,
                "delivery_address": delivery_address,
                "note": note,
                "status": "pending",
                "payment_status": "pending",
            }
            if delivery_lat is not None:
                data["delivery_lat"] = delivery_lat
            if delivery_lon is not None:
                data["delivery_lon"] = delivery_lon
            if delivery_fee is not None:
                data["delivery_fee"] = delivery_fee
            if quotation_id is not None:
                data["quotation_id"] = quotation_id
            if delivery_appointment is not None:
                data["delivery_appointment"] = delivery_appointment.isoformat() if hasattr(delivery_appointment, "isoformat") else delivery_appointment

            result = self._supabase_client.table(self._table_name) \
                .insert(data) \
                .execute()

            # Deliberately no _invalidate_seller_orders() here: the row is
            # inserted payment_status='pending' (set explicitly above) and the
            # seller signature only counts 'paid' rows, so an insert cannot move
            # it. The order enters the seller's list at update_payment_status,
            # which does invalidate. Drop the payment_status filter from
            # read_orders_head_by_seller_id and this stops being true.
            if result and result.data:
                return result.data[0]

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - create_order: {e}")
        except Exception as e:
            raise Exception(f"error create_order: {e}")

    def read_orders_by_user_id(self, user_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, seller_id, status, total_amount, delivery_fee, payment_status, delivery_method, delivery_appointment, created_at, seller_profiles(store_name, slug, avatar_url), refunds(status), reviews(id)") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(1, foreign_table="reviews") \
                .execute()

            if result and result.data:
                return result.data

            return []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_orders_by_user_id: {e}")
        except Exception as e:
            raise Exception(f"error read_orders_by_user_id: {e}")

    def read_order_by_id(self, order_id: str, user_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, seller_id, status, total_amount, delivery_fee, payment_status, transaction_ref, ipn_data, payment_create_date, delivery_method, delivery_address, delivery_appointment, note, cancellation_reason, created_at, seller_profiles(store_name, slug, avatar_url), order_items(id, food_item_id, name_snapshot, price_snapshot, unit_label_snapshot, quantity, food_items(image_url)), refunds(status)") \
                .eq("id", order_id) \
                .eq("user_id", user_id) \
                .maybe_single() \
                .execute()

            if result and result.data:
                return result.data

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_by_id: {e}")
        except Exception as e:
            raise Exception(f"error read_order_by_id: {e}")

    def read_orders_by_seller_id(self, seller_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, user_id, status, total_amount, delivery_fee, payment_status, delivery_method, delivery_address, delivery_appointment, note, created_at, users(name, phone, email), order_items(id, name_snapshot, price_snapshot, unit_label_snapshot, quantity)") \
                .eq("seller_id", seller_id) \
                .eq("payment_status", "paid") \
                .order("created_at", desc=True) \
                .execute()

            return result.data if result and result.data else []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_orders_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_orders_by_seller_id: {e}")

    def read_orders_head_by_seller_id(self, seller_id: str):
        """Signature of the seller's order list: newest updated_at + row count.

        Mirrors the payment_status filter of read_orders_by_seller_id so the
        signature tracks exactly the rows that list returns. Callers should read
        through the cache (see the /head route) rather than calling this on every
        poll tick — count="exact" counts the whole filtered set, it is not a
        single-row read.
        """
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("updated_at", count="exact") \
                .eq("seller_id", seller_id) \
                .eq("payment_status", "paid") \
                .order("updated_at", desc=True) \
                .limit(1) \
                .execute()

            latest = result.data[0]["updated_at"] if result and result.data else None
            return {"latest": latest, "count": result.count or 0}

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_orders_head_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_orders_head_by_seller_id: {e}")

    def read_order_by_id_for_seller(self, order_id: str, seller_id: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, user_id, status, total_amount, delivery_fee, payment_status, transaction_ref, ipn_data, payment_create_date, delivery_method, delivery_address, delivery_appointment, note, created_at, users(name, email), order_items(id, name_snapshot, price_snapshot, unit_label_snapshot, quantity)") \
                .eq("id", order_id) \
                .eq("seller_id", seller_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_by_id_for_seller: {e}")
        except Exception as e:
            raise Exception(f"error read_order_by_id_for_seller: {e}")

    def update_order_status(self, order_id: str, status: str, cancellation_reason: Optional[str] = None):
        try:
            update_data = {"status": status}
            if cancellation_reason:
                update_data["cancellation_reason"] = cancellation_reason

            result = self._supabase_client.table(self._table_name) \
                .update(update_data) \
                .eq("id", order_id) \
                .execute()

            if result and result.data:
                # The updated row carries seller_id, so the cache drop costs
                # nothing extra here.
                _invalidate_seller_orders(result.data[0].get("seller_id"))
                return result.data[0]

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_order_status: {e}")
        except Exception as e:
            raise Exception(f"error update_order_status: {e}")

    def read_order_by_id_raw(self, order_id: str):
        """Read order by ID without user scoping (for IPN server-to-server)."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, payment_status, status, total_amount") \
                .eq("id", order_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_by_id_raw: {e}")
        except Exception as e:
            raise Exception(f"error read_order_by_id_raw: {e}")

    def read_order_with_seller_coords(self, order_id: str):
        """Read order with seller profile coords for delivery booking."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, user_id, seller_id, seller_user_id, status, delivery_method, delivery_address, delivery_lat, delivery_lon, quotation_id, delivery_fee, seller_profiles(store_name, address, lat, lon, phone), users(name, phone, email)") \
                .eq("id", order_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_with_seller_coords: {e}")
        except Exception as e:
            raise Exception(f"error read_order_with_seller_coords: {e}")

    def update_payment_status(self, order_id: str, payment_status: str, transaction_ref: Optional[str] = None):
        try:
            self._supabase_client.rpc(
                'update_order_payment_status',
                {
                    'p_order_id': order_id,
                    'p_status': payment_status,
                    'p_transaction_ref': transaction_ref
                }
            ).execute()

            # The most important invalidation of the lot: pending -> paid is what
            # makes an order enter the seller's list in the first place. The RPC
            # returns void, so seller_id costs one primary-key read — once per
            # payment, against a cache that serves every poll tick in between.
            self._invalidate_cache_for_order(order_id)
            return True

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_payment_status: {e}")
        except Exception as e:
            raise Exception(f"error update_payment_status: {e}")

    def _invalidate_cache_for_order(self, order_id: str):
        """Drop the owning seller's cached signature for a write that did not
        hand back the row. Never let a cache problem break the write that
        already succeeded — a stale entry expires on its own within TTL_SECONDS.
        """
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("seller_id") \
                .eq("id", order_id) \
                .maybe_single() \
                .execute()

            if result and result.data:
                _invalidate_seller_orders(result.data.get("seller_id"))

        except Exception as e:
            logger.warning(f"order cache invalidate failed for order {order_id}: {e}")

    def update_payment_create_date(self, order_id: str, payment_create_date: str):
        try:
            result = self._supabase_client.table(self._table_name) \
                .update({"payment_create_date": payment_create_date}) \
                .eq("id", order_id) \
                .execute()

            if result and result.data:
                _invalidate_seller_orders(result.data[0].get("seller_id"))
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_payment_create_date: {e}")
        except Exception as e:
            raise Exception(f"error update_payment_create_date: {e}")

    def update_ipn_data(self, order_id: str, ipn_data: dict):
        try:
            result = self._supabase_client.table(self._table_name) \
                .update({"ipn_data": ipn_data}) \
                .eq("id", order_id) \
                .execute()

            if result and result.data:
                _invalidate_seller_orders(result.data[0].get("seller_id"))
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_ipn_data: {e}")
        except Exception as e:
            raise Exception(f"error update_ipn_data: {e}")
