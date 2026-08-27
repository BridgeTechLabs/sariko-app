-- Follow-up to 20260824_food_item_variants.sql: RLS for the new table.
--
-- The table migration created food_item_variants but left RLS off, while every
-- sibling table (food_items, cart_items, order_items) has it on. Probed with the
-- public anon key from the frontend bundle: GET /rest/v1/food_item_variants
-- returned 200, not 401 — role `anon` holds a SELECT grant, so once sellers add
-- price levels anyone with that key could read them. Enabling RLS closes read
-- AND write in one step; the backend is unaffected because it uses service_role,
-- which bypasses RLS entirely.
--
-- Policies mirror food_items: a price level is no more sensitive than the dish
-- price it belongs to, and ownership is checked one hop up through the parent dish.
-- Idempotent (drop-if-exists before create), same convention as policies/rls.sql.
-- Run once against the live Supabase database.

begin;

alter table public.food_item_variants enable row level security;

drop policy if exists "public read variants" on public.food_item_variants;
create policy "public read variants"
on public.food_item_variants for select
using (is_available = true);

drop policy if exists "seller manage variants" on public.food_item_variants;
create policy "seller manage variants"
on public.food_item_variants for all
using (food_item_id in (
  select fi.id from public.food_items fi
  join public.seller_profiles sp on sp.id = fi.seller_id
  where sp.user_id = auth.uid()))
with check (food_item_id in (
  select fi.id from public.food_items fi
  join public.seller_profiles sp on sp.id = fi.seller_id
  where sp.user_id = auth.uid()));

commit;


-- ── Kiểm tra sau khi chạy (read-only) ───────────────────────────────────────
-- select relrowsecurity from pg_class
--  where oid = 'public.food_item_variants'::regclass;      -- expect: t
--
-- select policyname, cmd from pg_policies
--  where schemaname = 'public' and tablename = 'food_item_variants';
--   -- expect: "public read variants" (SELECT), "seller manage variants" (ALL)
