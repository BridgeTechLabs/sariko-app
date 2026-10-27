import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from core.sariko_cache import cache
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_base import DAOBase
from dao.dao_refunds import DAORefunds
from services import push_service, zalo

logger = logging.getLogger(__name__)

SOLD_OUT_REASON = "Sold out"  # the buyer UI translates this exact text (OrderStatusHeader.vue)


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
        subtotal: Decimal, total_amount: Decimal,
        commission_rate: Decimal, commission_amount: Decimal,
        vat_rate: Decimal, vat_amount: Decimal,
        payout_amount: Decimal,
        delivery_method: str, delivery_address: Optional[str] = None, note: Optional[str] = None,
        delivery_lat: Optional[float] = None, delivery_lon: Optional[float] = None,
        delivery_fee: Optional[int] = None, quotation_id: Optional[str] = None,
        delivery_appointment=None
    ):
        try:
            data = {
                "user_id": user_id,
                "seller_id": seller_id,
                "seller_user_id": seller_user_id,
                # numeric columns; PostgREST's JSON body can't carry a Decimal
                "subtotal": str(subtotal),
                "total_amount": str(total_amount),
                "commission_rate": str(commission_rate),
                "commission_amount": str(commission_amount),
                "vat_rate": str(vat_rate),
                "vat_amount": str(vat_amount),
                "payout_amount": str(payout_amount),
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
                .select("id, seller_id, status, total_amount, delivery_fee, payment_status, delivery_method, delivery_appointment, created_at, seller_profiles(store_name, slug, avatar_url), refunds(status), review_stores(id), deliveries(status)") \
                .eq("user_id", user_id) \
                .neq("refunds.reason", "duplicate_payment") \
                .order("created_at", desc=True) \
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
                .select("id, seller_id, status, total_amount, delivery_fee, payment_status, transaction_ref, ipn_data, payment_create_date, delivery_method, delivery_address, delivery_appointment, note, cancellation_reason, status_changed_at, created_at, seller_profiles(store_name, slug, avatar_url), order_items(id, food_item_id, name_snapshot, price_snapshot, unit_label_snapshot, variant_name_snapshot, quantity, food_items(image_url)), refunds(status)") \
                .eq("id", order_id) \
                .eq("user_id", user_id) \
                .neq("refunds.reason", "duplicate_payment") \
                .maybe_single() \
                .execute()

            if result and result.data:
                return result.data

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_by_id: {e}")
        except Exception as e:
            raise Exception(f"error read_order_by_id: {e}")

    _SELLER_LIST_SELECT = "id, user_id, status, total_amount, delivery_fee, payment_status, delivery_method, delivery_address, delivery_appointment, note, created_at, paid_at, status_changed_at, users{join}(name, phone, email), order_items(id, name_snapshot, price_snapshot, unit_label_snapshot, variant_name_snapshot, quantity), deliveries(status)"

    def read_orders_by_seller_id(self, seller_id: str, finished_since: datetime):
        """Running orders of any age + done / cancelled orders created since `finished_since` (UTC)."""
        # orders.created_at is timestamp without time zone holding UTC: compare against naive UTC.
        since = finished_since.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
        try:
            result = self._supabase_client.table(self._table_name) \
                .select(self._SELLER_LIST_SELECT.format(join="")) \
                .eq("seller_id", seller_id) \
                .eq("payment_status", "paid") \
                .or_(f"status.not.in.(done,cancelled),created_at.gte.{since}") \
                .order("created_at", desc=True) \
                .execute()

            return result.data if result and result.data else []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_orders_by_seller_id: {e}")
        except Exception as e:
            raise Exception(f"error read_orders_by_seller_id: {e}")

    def read_done_orders_for_earnings(self, seller_id: str, done_since: datetime):
        """Seller's paid orders that became done since `done_since`, with their money split."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, subtotal, commission_amount, vat_amount, payout_amount, payout_status, payout_hold, status_changed_at, wh_vat_amount, wh_pit_amount") \
                .eq("seller_id", seller_id) \
                .eq("payment_status", "paid") \
                .eq("status", "done") \
                .gte("status_changed_at", done_since.isoformat()) \
                .order("status_changed_at", desc=True) \
                .execute()

            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_done_orders_for_earnings: {e}")
        except Exception as e:
            raise Exception(f"error read_done_orders_for_earnings: {e}")

    def search_orders_for_seller(self, seller_id: str, code: Optional[str], name: Optional[str], limit: int):
        """Seller order search, any age. `code`: lowercase hex prefix of the order id;
        `name`: substring of the buyer's name (caller strips filter characters)."""
        def query(join):
            return self._supabase_client.table(self._table_name) \
                .select(self._SELLER_LIST_SELECT.format(join=join)) \
                .eq("seller_id", seller_id) \
                .eq("payment_status", "paid") \
                .order("created_at", desc=True) \
                .limit(limit)

        def as_uuid(hex32):
            return f"{hex32[:8]}-{hex32[8:12]}-{hex32[12:16]}-{hex32[16:20]}-{hex32[20:]}"

        try:
            found = {}
            if code:
                # uuid has no LIKE: a prefix is the range [prefix000…, prefixfff…].
                rows = query("").gte("id", as_uuid((code + "0" * 32)[:32])) \
                    .lte("id", as_uuid((code + "f" * 32)[:32])).execute().data or []
                found.update({r["id"]: r for r in rows})
            if name:
                rows = query("!inner").ilike("users.name", f"*{name}*").execute().data or []
                found.update({r["id"]: r for r in rows})
            return sorted(found.values(), key=lambda r: r["created_at"], reverse=True)[:limit]

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - search_orders_for_seller: {e}")
        except Exception as e:
            raise Exception(f"error search_orders_for_seller: {e}")

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
                .select("id, user_id, status, total_amount, delivery_fee, payment_status, transaction_ref, ipn_data, payment_create_date, delivery_method, delivery_address, delivery_appointment, note, cancellation_reason, created_at, paid_at, status_changed_at, users(name, email, phone), order_items(id, name_snapshot, price_snapshot, unit_label_snapshot, variant_name_snapshot, quantity), payments(method, type)") \
                .eq("id", order_id) \
                .eq("seller_id", seller_id) \
                .maybe_single() \
                .execute()

            return result.data if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_order_by_id_for_seller: {e}")
        except Exception as e:
            raise Exception(f"error read_order_by_id_for_seller: {e}")

    def read_status_history(self, order_id: str):
        """[{status, changed_at}] oldest first, written by the log_order_status trigger.
        Orders older than that trigger (2026-10-16) have none."""
        try:
            result = self._supabase_client.table("history_order_status") \
                .select("status, changed_at") \
                .eq("order_id", order_id) \
                .order("changed_at") \
                .execute()

            return result.data or []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_status_history: {e}")
        except Exception as e:
            raise Exception(f"error read_status_history: {e}")

    def update_order_status(self, order_id: str, status: str, cancellation_reason: Optional[str] = None,
                            expected_status: Optional[str] = None):
        """expected_status makes the write conditional: if someone else changed the
        status first (seller vs the confirm-timeout job), nothing is written and
        None comes back."""
        try:
            update_data = {"status": status}
            if cancellation_reason:
                update_data["cancellation_reason"] = cancellation_reason

            query = self._supabase_client.table(self._table_name) \
                .update(update_data) \
                .eq("id", order_id)
            if expected_status:
                query = query.eq("status", expected_status)
            result = query.execute()

            if result and result.data:
                # The updated row carries seller_id, so the cache drop costs
                # nothing extra here.
                _invalidate_seller_orders(result.data[0].get("seller_id"))
                # Every status change funnels through here (seller, Lalamove
                # webhook, auto-cancel, dev panel), so this is the one hook.
                push_service.notify_order_status(result.data[0])
                return result.data[0]

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_order_status: {e}")
        except Exception as e:
            raise Exception(f"error update_order_status: {e}")

    def read_unconfirmed_paid_orders(self, paid_before: datetime):
        """Paid orders still waiting for the seller, paid before `paid_before`, with the
        store hours needed to decide whether they timed out (or are about to)."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, seller_user_id, total_amount, payment_status, transaction_ref, ipn_data, payment_create_date, paid_at, "
                        "seller_profiles(is_open, opening_time, closing_time, opened_at)") \
                .eq("status", "pending") \
                .eq("payment_status", "paid") \
                .lte("paid_at", paid_before.isoformat()) \
                .execute()

            return result.data if result and result.data else []

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_unconfirmed_paid_orders: {e}")
        except Exception as e:
            raise Exception(f"error read_unconfirmed_paid_orders: {e}")

    def read_order_by_id_raw(self, order_id: str):
        """Read order by ID without user scoping (for IPN server-to-server)."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .select("id, seller_user_id, payment_status, status, total_amount, transaction_ref, delivery_appointment, seller_profiles(store_name)") \
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
            # T134: the order takes its dish portions before it reaches the seller. The last portion
            # going while the buyer paid: still marked paid (the money came in), then cancelled + refunded.
            sold_out = payment_status == "paid" and not self._supabase_client.rpc(
                'reserve_order_portions', {'p_order_id': order_id}).execute().data
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

            if sold_out:
                self._cancel_sold_out(order_id)
                return True

            # Same rule as the cache drop: the payment is already written, so a
            # failed push lookup must not turn the IPN into an error.
            if payment_status == "paid":
                # Seller tax withholding snapshot (Decree 252, per order at payment). A failure
                # must not fail the IPN: the payout computes the missing orders first.
                try:
                    self._supabase_client.rpc('compute_order_withholding', {'p_order_id': order_id}).execute()
                except Exception as e:
                    logger.error(f"withholding not computed for order {order_id}, payout will compute it: {e}")
                try:
                    order = self.read_order_by_id_raw(order_id)
                    if order:
                        push_service.notify_new_order(order)
                        # T136: the team's Zalo group; zalo_new_order_alerts 0 turns it off when orders get many
                        if zalo.configured("orders") and DAOAdminConfig().get_int_in_range("zalo_new_order_alerts", 1, 0, 1):
                            zalo.send("orders", zalo.new_order_text(order))
                except Exception as e:
                    logger.warning(f"new-order push / Zalo skipped for order {order_id}: {e}")
            return True

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_payment_status: {e}")
        except Exception as e:
            raise Exception(f"error update_payment_status: {e}")

    def _cancel_sold_out(self, order_id: str):
        """docs/dev/daily-portions Q3: no seller push; the status hook pushes the buyer, a full refund is queued."""
        cancelled = self.update_order_status(order_id, "cancelled", SOLD_OUT_REASON, expected_status="pending")
        if cancelled:
            DAORefunds().create_refund_for_order(cancelled, "sold_out")
        logger.warning(f"order {order_id} paid but a dish sold out meanwhile: cancelled, refund queued")

    def touch_order(self, order_id: str):
        """Bump orders.updated_at (the on_orders_update trigger sets it) and drop the
        seller's cached signature. The order lists show the delivery status, so a
        delivery-only change must still move the list signature the seller polls."""
        try:
            self._supabase_client.table(self._table_name) \
                .update({"updated_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", order_id) \
                .execute()
            self._invalidate_cache_for_order(order_id)
        except Exception as e:
            logger.warning(f"touch_order failed for {order_id}: {e}")

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
            # A new pay link: the querydr state of the previous one no longer applies (T125)
            result = self._supabase_client.table(self._table_name) \
                .update({"payment_create_date": payment_create_date, "vnpay_checked_at": None,
                         "vnpay_check": None, "vnpay_fail_notified_at": None}) \
                .eq("id", order_id) \
                .execute()

            if result and result.data:
                _invalidate_seller_orders(result.data[0].get("seller_id"))
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_payment_create_date: {e}")
        except Exception as e:
            raise Exception(f"error update_payment_create_date: {e}")

    # T125: what the VNPay check (querydr) needs about an unpaid order, with refunds (never asked
    # about: querydr after a refund still answers "paid") and payment rows (an IPN result is final).
    _VNPAY_STATE = ("id, user_id, status, payment_status, total_amount, payment_create_date, vnpay_checked_at, "
                    "vnpay_check, vnpay_fail_notified_at, refunds(id), payments(transaction_ref, status)")

    def read_vnpay_state(self, order_id: str):
        try:
            result = self._supabase_client.table(self._table_name).select(self._VNPAY_STATE) \
                .eq("id", order_id).maybe_single().execute()
            return result.data if result and result.data else None
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_vnpay_state: {e}")

    def read_unpaid_vnpay_orders(self, created_since: datetime):
        """Unpaid orders that got a VNPay pay link, created since `created_since` (UTC)."""
        try:
            return self._supabase_client.table(self._table_name).select(self._VNPAY_STATE) \
                .eq("payment_status", "pending") \
                .not_.is_("payment_create_date", "null") \
                .gte("created_at", created_since.astimezone(timezone.utc).replace(tzinfo=None).isoformat()) \
                .execute().data or []
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_unpaid_vnpay_orders: {e}")

    def claim_vnpay_check(self, order_id: str, now: datetime, last_before: datetime) -> bool:
        """Take this order's turn to ask VNPay: true only for the caller whose conditional update set
        vnpay_checked_at (never asked, or last asked before `last_before`). The job and a buyer's new-link
        request can't both ask (a second ask within ~15 minutes gets 94)."""
        try:
            result = self._supabase_client.table(self._table_name) \
                .update({"vnpay_checked_at": now.isoformat()}).eq("id", order_id) \
                .or_(f"vnpay_checked_at.is.null,vnpay_checked_at.lt.{last_before.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ}").execute()
            return bool(result.data)
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - claim_vnpay_check: {e}")

    def save_vnpay_check(self, order_id: str, check: dict, checked_at: datetime):
        try:
            self._supabase_client.table(self._table_name) \
                .update({"vnpay_check": check, "vnpay_checked_at": checked_at.isoformat()}).eq("id", order_id).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - save_vnpay_check: {e}")

    def set_vnpay_fail_notified(self, order_id: str, at: datetime):
        try:
            self._supabase_client.table(self._table_name) \
                .update({"vnpay_fail_notified_at": at.isoformat()}).eq("id", order_id).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - set_vnpay_fail_notified: {e}")

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
