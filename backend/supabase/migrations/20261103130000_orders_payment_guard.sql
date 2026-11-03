-- Incident 2026-11-02: update_order_status() has no payment check, and the admin
-- service-role key bypasses RLS, so a compromised session could push unpaid orders
-- straight to confirmed/ready/done. Enforce it at the DB layer instead, where no
-- write path (including service-role) can skip it.
alter table public.orders
  add constraint orders_paid_before_progress_check check (
    payment_status = 'paid' or status not in ('confirmed', 'ready', 'done', 'delivery_failed')
  );
