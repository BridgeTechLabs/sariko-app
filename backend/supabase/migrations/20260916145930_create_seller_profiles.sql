-- ============================================================
-- Seller profiles
-- tier FK → admin_tier_config; status coming_soon | active.
-- ============================================================

create table if not exists public.seller_profiles (
  id uuid not null default gen_random_uuid (),
  user_id uuid null,
  store_name text not null,
  description text null,
  avatar_url text null,
  cover_url text null,
  address text null,
  lat numeric null,
  lon numeric null,
  is_open boolean null default true,
  opening_time time without time zone null,
  closing_time time without time zone null,
  is_verified boolean null default false,
  created_at timestamp without time zone null default now(),
  slug text not null,
  phone text null,
  tier text not null default 'community'::text,
  commission_rate_override numeric null,
  bank_account_number text null,
  bank_name text null,
  bank_account_holder text null,
  tax_category text not null default 'services'::text,
  status text not null default 'coming_soon'::text,
  rating_avg numeric null,
  rating_count integer not null default 0,
  is_listed boolean not null default true,
  display_order integer not null default 0,
  constraint seller_profiles_pkey primary key (id),
  constraint seller_profiles_slug_key unique (slug),
  constraint seller_profiles_tier_fkey foreign KEY (tier) references admin_tier_config (tier),
  constraint seller_profiles_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE,
  constraint seller_profiles_tax_category_check check (
    (tax_category = any (array['goods'::text, 'services'::text]))
  ),
  constraint seller_profiles_status_check check (
    (status = any (array['coming_soon'::text, 'active'::text]))
  )
) TABLESPACE pg_default;

create index IF not exists idx_seller_location on public.seller_profiles using btree (lat, lon) TABLESPACE pg_default;

comment on column public.seller_profiles.commission_rate_override is
  'Only set for bodega tier. NULL = use admin_tier_config.commission_rate.';
comment on column public.seller_profiles.rating_avg is
  'Denormalised from reviews (overall rows only, food_item_id is null). Maintained by
   the on_review_change trigger — never write it by hand. NULL until the first review.';
comment on column public.seller_profiles.is_listed is
  'Admin curation: false = hidden from the public seller list and from featured dishes.
   Distinct from status (lifecycle: coming_soon | active) and is_open (opening hours) —
   a seller can be active + open and still be unlisted. The storefront stays reachable
   by direct slug URL; this only controls discovery.';
comment on column public.seller_profiles.display_order is
  'Manual sort within the seller list, ascending (lower first). Applied after status,
   so it orders sellers within the active block and within the coming_soon block.
   Ties break by created_at.';
