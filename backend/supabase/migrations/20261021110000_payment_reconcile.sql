-- ============================================================
-- T125: confirm a VNPay payment when the IPN is late or never comes (docs/dev/payment-confirm/README.md).
-- * 3 parameters: when the backend starts asking VNPay (querydr), when it stops, how long the payment result
--   page waits before saying "waiting for VNPay" (never "failed" because of a timeout).
-- * orders.vnpay_checked_at / vnpay_check: the last querydr answer for the order's current pay link
--   (VNPay answers 94 "Request is duplicated" to the same transaction within ~15 minutes, so the backend asks
--   at most once per 15 minutes and reuses this answer in between). vnpay_fail_notified_at: the buyer was told
--   once that this link was not paid. All three reset when a new pay link is made.
-- ============================================================

insert into public.admin_settings (key, value, description) values
  ('payment_reconcile_after_minutes', '5'::jsonb,
   'Minutes after a VNPay pay link is made, with no IPN yet, before the backend asks VNPay for the result (querydr).'),
  ('payment_reconcile_window_hours', '24'::jsonb,
   'Hours after a VNPay pay link is made after which the backend stops asking VNPay about it.'),
  ('payment_result_wait_seconds', '90'::jsonb,
   'Seconds the payment result page waits for the confirmation before it says it is waiting for VNPay (it never says failed because of the wait).')
on conflict (key) do nothing;

alter table public.orders
  add column if not exists vnpay_checked_at timestamptz,
  add column if not exists vnpay_check jsonb,
  add column if not exists vnpay_fail_notified_at timestamptz;
comment on column public.orders.vnpay_check is
  'Last querydr answer (signed fields) for the current pay link (vnp_TxnRef = id without dashes + "_" + payment_create_date). Reset with a new link.';
