-- Seed: tier definitions. Must run before any seller_profiles row
-- (seller_profiles.tier FK → admin_tier_config.tier, default 'community').
insert into public.admin_tier_config (tier, commission_rate, monthly_fee_usd, monthly_fee_vnd, max_items, max_categories)
values
  ('founding',   0.17, 29, 720000,  null, null),  -- 50 early sellers: tindahan price, no monthly fee for 4 months (not billed yet, T49)
  ('community',  0.19, 0,  0,       3,    1),
  ('tindahan',   0.17, 29, 720000,  30,   5),
  ('negosyo',    0.15, 49, 1200000, 90,   10),
  ('enterprise', 0.13, 89, 2200000, null, null),
  ('bodega',     0,    0,  0,       null, null)   -- negotiated: rate set via seller_profiles.commission_rate_override
on conflict (tier) do nothing;
