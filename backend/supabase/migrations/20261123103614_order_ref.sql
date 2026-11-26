-- ============================================================
-- Which AI Studio post an order came from (docs/dev/20261123-studio-integration QĐ-1). A Studio link opens
-- /seller/<slug>?ref=<post code>&utm_source=<channel>; the app keeps it and create_order stores it on an order of
-- that store placed within attribution_window_days. Null = no post. Nullable columns: no table rewrite, and the
-- running backend keeps inserting without them.
-- ============================================================

alter table public.orders
  add column if not exists ref_code   text check (ref_code ~ '^[A-Za-z0-9_-]{1,64}$'),
  add column if not exists ref_source text check (ref_source ~ '^[a-z0-9_]{1,32}$');

insert into public.admin_settings (key, value, description)
values ('attribution_window_days', '7'::jsonb,
        'Days (integer > 0) after a buyer last opened an AI Studio post link during which their orders at that store count for the post.')
on conflict (key) do nothing;
