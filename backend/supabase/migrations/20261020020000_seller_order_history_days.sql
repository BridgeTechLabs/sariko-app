-- ============================================================
-- How far back the seller's order list goes for finished orders (seller-ui-review P1-3).
-- Running orders are always listed; done / cancelled ones only for this many days,
-- older ones are found through the order search. Integer > 0; the backend falls back
-- to 30 if the row is missing or invalid (dao_admin_config.get_positive_int).
-- Expand-only: the running backend ignores rows it doesn't know.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('seller_order_history_days', '30'::jsonb,
   'Days (integer > 0) of done and cancelled orders shown in the seller''s order list and earnings. Running orders are always shown; older orders are found by searching the order code or buyer name.')
on conflict (key) do nothing;
