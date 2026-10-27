-- ============================================================
-- Ops messages to the team's Zalo group (docs/dev/zalo-alerts, T136). Each paid order sends one
-- "new order" message; this switch turns only that one off when orders get many (dao_orders,
-- get_int_in_range 0..1, default 1). Expand-only.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('zalo_new_order_alerts', '1'::jsonb,
   'New-order messages in the team''s Zalo group: 1 = every paid order sends one message, 0 = off (when there are many orders). Complaints, refunds and delivery problems are always sent.')
on conflict (key) do nothing;
