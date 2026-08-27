-- Migration: listing controls on seller_profiles
--   is_listed     — admin curation: show / hide a seller in the public list
--   display_order — manual ordering within that list (ascending, lower first)
-- Run once against the live Supabase database.

alter table public.seller_profiles
  add column if not exists is_listed boolean not null default true;

alter table public.seller_profiles
  add column if not exists display_order integer not null default 0;

-- No backfill needed: default true keeps every existing seller visible,
-- default 0 leaves them all tied and ordered by created_at.

comment on column public.seller_profiles.is_listed is
  'Admin curation: false = hidden from the public seller list and from featured dishes.
   Distinct from status (lifecycle: coming_soon | active) and is_open (opening hours) —
   a seller can be active + open and still be unlisted. The storefront stays reachable
   by direct slug URL; this only controls discovery.';
comment on column public.seller_profiles.display_order is
  'Manual sort within the seller list, ascending (lower first). Applied after status,
   so it orders sellers within the active block and within the coming_soon block.
   Ties break by created_at.';
