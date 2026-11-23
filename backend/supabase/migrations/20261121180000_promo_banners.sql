-- ============================================================
-- Banners of the buyer home page, at the top or just above the footer (docs/dev/20261121-promo-banners).
-- The admin app adds / orders / switches / deletes them (images uploaded to Storage); the app's public GET /promo-banners reads the
-- active ones. No seed: an empty position shows no carousel. Safe to run twice.
-- ============================================================

create table if not exists public.admin_promo_banners (
  id          uuid        primary key default gen_random_uuid(),
  image_url   text        not null check (image_url ~ '^https://'),
  link_url    text        not null check (link_url ~ '^https://'),
  alt         text        not null default '' check (length(alt) <= 120),
  placement   text        not null default 'top' check (placement in ('top', 'footer')),
  position    integer     not null,   -- order within its placement
  is_active   boolean     not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
alter table public.admin_promo_banners enable row level security;   -- service role only (both backends), no policy
comment on table public.admin_promo_banners is
  'Buyer home banners (top / footer), shown by position then created_at (docs/dev/20261121-promo-banners).';

insert into public.admin_settings (key, value, description)
values ('promo_banner_max', '10'::jsonb,
        'Most banners (integer > 0) per position (top / footer) of the buyer home page. The admin page refuses to add more there; the home page shows at most this many.')
on conflict (key) do nothing;
