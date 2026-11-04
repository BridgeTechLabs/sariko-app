-- ============================================================
-- Seller payouts every few days (docs/dev/payout-cycle/README.md §6; Jack 2026-10-22).
-- Every payout_cycle_days days from payout_cycle_start_date is a payout day P; P pays the orders
-- done (Vietnam date) from P - payout_delay_days - payout_cycle_days + 1 to P - payout_delay_days.
-- 99991231 = cycle off: one day at a time as before (done day + payout_delay_days).
-- Read by the admin backend (GET /admin/payouts/next-period, Generate defaults) and the seller
-- Earnings page (expected payout day). admin_generate_payouts is unchanged: it still only
-- refuses a period ending after today - payout_delay_days.
-- Expand-only: the running backend ignores rows it doesn't know.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('payout_cycle_days', '3'::jsonb,
   'Days (integer 1-14) between two seller payout days, counted from payout_cycle_start_date. Each payout day pays the orders done in the previous payout_cycle_days days that are at least payout_delay_days old. Invalid values fall back to 1 (every day).'),
  ('payout_cycle_start_date', '99991231'::jsonb,
   'First seller payout day of the cycle (YYYYMMDD, Vietnam date). 99991231 = cycle off: orders are paid one day at a time, payout_delay_days after they are done.')
on conflict (key) do nothing;
