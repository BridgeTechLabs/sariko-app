-- ============================================================
-- Refund reason for an order cancelled by an admin (admin repo, Orders page;
-- docs/dev/order-cancel-refund.md R10). Expand-only: this app never writes it.
-- ============================================================

alter table public.refunds drop constraint if exists refunds_reason_check;
alter table public.refunds add constraint refunds_reason_check check (
  reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text, 'seller_cancel'::text,
                      'seller_timeout'::text, 'admin_cancel'::text])
);
