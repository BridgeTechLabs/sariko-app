-- Incident 2026-11-02: update_order_status() has no payment check, and the admin
-- service-role key bypasses RLS, so a compromised session could push unpaid orders
-- straight to confirmed/ready/done. Enforce it at the DB layer so no write that
-- only changes `status` (the actual gap exploited) can do that again; a write that
-- sets both columns at once (always possible with the service-role key) is out of
-- scope for a CHECK constraint. coalesce() also closes the NULL loophole (NULL in
-- a CHECK reads as "not violated").
-- NOT VALID: checks every insert / update from now on, skips existing rows. PROD keeps
-- one unpaid "done" order of a banned 2026-11-02 attack account as evidence; a
-- validating add would abort this migration on it.
alter table public.orders
  add constraint orders_paid_before_progress_check check (
    coalesce(payment_status, '') = 'paid' or status not in ('confirmed', 'ready', 'done', 'delivery_failed')
  ) not valid;
