-- ============================================================
-- Refund reason 'late_payment' (spec docs/dev/vnpay-doc-align B4): VNPay confirms a
-- payment for an order that no longer waits for it (the buyer cancelled while paying).
-- The IPN no longer marks such an order paid; it queues a full refund for the admin.
-- Expand-only: adds one allowed value.
-- ============================================================
alter table public.refunds drop constraint if exists refunds_reason_check;
alter table public.refunds add constraint refunds_reason_check check (
  reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text, 'seller_cancel'::text,
                      'seller_timeout'::text, 'admin_cancel'::text, 'late_payment'::text])
);
