-- ============================================================
-- T179 A15 (docs/dev/20261110-admin-kpi): the admin Orders page counts a ready delivery order as stuck only once its
-- current trip has had no driver for this long (it counted from the first second). 15 minutes = the seller app's
-- "trip stuck, contact support" mark. Read by the admin backend only. Insert only.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('stuck_no_driver_minutes', '15'::jsonb,
   'A ready delivery order whose current trip has had no driver for this many minutes counts as a stuck order on the admin Orders page.')
on conflict (key) do nothing;
