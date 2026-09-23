-- Seed: tier definitions. Must run before any seller_profiles row
-- (seller_profiles.tier FK → admin_tier_config.tier, default 'community').
insert into public.admin_tier_config (tier, commission_rate, monthly_fee_usd, max_items, max_categories)
values
  ('founding',   0,    0,  null, null),  -- 0% commission, early adopter sellers
  ('community',  0.19, 0,  3,    1),
  ('tindahan',   0.17, 29, 30,   5),
  ('negosyo',    0.15, 49, 90,   10),
  ('enterprise', 0.13, 89, null, null),
  ('bodega',     0,    0,  null, null)   -- negotiated: rate set via seller_profiles.commission_rate_override
on conflict (tier) do nothing;
