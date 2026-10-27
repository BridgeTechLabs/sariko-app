-- ============================================================
-- Duplicate VNPay payments get their own refund (spec docs/dev/vnpay-doc-align B7).
-- A buyer can open two payment URLs for one order and pay both: the second IPN used to
-- be answered "already confirmed" and the money stayed with SariKo.
--   * reason 'duplicate_payment': refund of an extra payment (TxnRef other than the order's).
--   * refunds_order_id_key stays "one MAIN refund per order" (cancel paths race on it),
--     now excluding duplicate_payment rows.
--   * refunds_order_txn_dup_key: one duplicate_payment refund per (order, TxnRef), so a
--     VNPay retry of the same IPN can't queue it twice. coalesce() instead of NULLS NOT
--     DISTINCT so it doesn't depend on the Postgres version.
-- No ON CONFLICT anywhere targets refunds (checked 2026-10-20: migrations, admin SQL,
-- both backends); admin_purge_orders deletes refunds by order_id, every reason included.
-- ============================================================
alter table public.refunds drop constraint if exists refunds_reason_check;
alter table public.refunds add constraint refunds_reason_check check (
  reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text, 'seller_cancel'::text,
                      'seller_timeout'::text, 'admin_cancel'::text, 'late_payment'::text,
                      'duplicate_payment'::text])
);

drop index if exists public.refunds_order_id_key;
create unique index refunds_order_id_key on public.refunds (order_id)
  where reason <> 'duplicate_payment';

create unique index if not exists refunds_order_txn_dup_key
  on public.refunds (order_id, coalesce(original_txn_ref, ''))
  where reason = 'duplicate_payment';
