-- ============================================================
-- AllinGo, a second delivery company next to Lalamove (docs/dev/20261109-allingo-delivery, T161).
-- deliveries.provider says which company booked the trip; an AllinGo trip keeps its "ord_..." id here,
-- a Lalamove trip keeps lalamove_order_id (the admin repo reads both). Existing columns are unchanged.
-- Indexes / constraints of deliveries read on PROD and DEV on 2026-11-09: the same 5 indexes, 4 constraints.
-- ============================================================

alter table public.deliveries add column if not exists allingo_order_id text;
create index if not exists idx_deliveries_allingo_order_id on public.deliveries using btree (allingo_order_id);

insert into public.admin_settings (key, value, description)
values
  ('delivery_provider_allingo', '0'::jsonb,
   'Which delivery company books new trips: 0 = Lalamove, 1 = AllinGo. Trips already booked stay with their company.')
on conflict (key) do nothing;
