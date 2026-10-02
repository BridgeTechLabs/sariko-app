-- ============================================================
-- Admin config: tier subscription + tax settings
-- Created FIRST — seller_profiles.tier and order snapshots FK / read from here.
-- ============================================================

create table if not exists public.admin_tier_config (
  tier            text    not null,
  commission_rate numeric not null,
  monthly_fee_usd numeric not null default 0,
  max_items       integer,      -- null = unlimited
  max_categories  integer,      -- null = unlimited
  constraint admin_tier_config_pkey primary key (tier)
);


comment on table public.admin_tier_config is
  'Source of truth for tier definitions. Changing commission_rate here does NOT affect past orders.';
comment on column public.admin_tier_config.commission_rate is
  'Default rate for this tier. Bodega = 0 because rate is negotiated per seller.';


create table if not exists public.admin_tax_config (
  key         text        not null,
  rate        numeric     not null,
  description text,
  updated_at  timestamptz not null default now(),
  constraint admin_tax_config_pkey primary key (key)
);


comment on table public.admin_tax_config is
  'Platform-wide tax settings. Adjustable by admin. Changes apply to new orders only.';
