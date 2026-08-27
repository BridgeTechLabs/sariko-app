-- Migration: per-dish price variants (one required, single-select group)
--   food_item_variants                — the selectable price levels
--   cart_items.variant_id             — cart holds a REFERENCE (price stays live)
--   order_items.variant_name_snapshot — order holds a SNAPSHOT (price frozen)
--
-- Why absolute prices: with a single-select group the variant REPLACES the dish
-- price, so nothing ever adds base + delta. order_items.price_snapshot therefore
-- keeps meaning "final unit price paid", and every existing
-- `price_snapshot * quantity` on the frontend keeps working untouched.
--
-- Dishes with no variants are unaffected: no variant rows exist and
-- food_items.price remains the price. No backfill needed.
--
-- There is deliberately no group-label column on food_items. The presence of
-- variant rows is the single source of truth for "does this dish have levels?",
-- so the two can never disagree, and the UI heading is a translated string in
-- the frontend rather than seller-typed text that no locale file can reach.
--
-- Wrapped in a transaction on purpose: step 3 deletes rows, so if any later
-- statement fails those deletes must roll back too.
-- Run once against the live Supabase database.

begin;

create table if not exists public.food_item_variants (
  id uuid not null default gen_random_uuid (),
  food_item_id uuid not null,
  name text not null,
  price numeric not null,
  price_text text null,
  sort_order integer not null default 0,
  is_available boolean not null default true,
  created_at timestamp without time zone null default now(),
  constraint food_item_variants_pkey primary key (id),
  constraint food_item_variants_food_item_id_fkey foreign KEY (food_item_id)
    references food_items (id) on delete CASCADE,
  -- Two variants of one dish may not share a name; the name is what the buyer
  -- picks by and what gets snapshotted onto the order.
  constraint food_item_variants_food_item_id_name_key unique (food_item_id, name),
  constraint food_item_variants_price_check check ((price >= (0)::numeric))
) TABLESPACE pg_default;

create index IF not exists idx_food_item_variants_item
  on public.food_item_variants using btree (food_item_id) TABLESPACE pg_default;

alter table public.cart_items
  add column if not exists variant_id uuid null;

do $$ begin
  alter table public.cart_items
    add constraint cart_items_variant_id_fkey foreign KEY (variant_id)
      references food_item_variants (id);
exception when duplicate_object then null;
end $$;

update public.cart_items ci
set quantity = t.total
from (
  select cart_id, food_item_id, sum(quantity) as total
  from public.cart_items
  group by cart_id, food_item_id
  having count(*) > 1
) t
where ci.cart_id = t.cart_id
  and ci.food_item_id = t.food_item_id
  and not exists (
    select 1 from public.cart_items older
    where older.cart_id = ci.cart_id
      and older.food_item_id = ci.food_item_id
      and older.id < ci.id
  );

delete from public.cart_items ci
where exists (
  select 1 from public.cart_items keep
  where keep.cart_id = ci.cart_id
    and keep.food_item_id = ci.food_item_id
    and keep.id < ci.id
);

alter table public.cart_items
  drop constraint if exists cart_items_cart_id_food_item_id_key;

create unique index IF not exists cart_items_dish_variant_key
  on public.cart_items using btree (cart_id, food_item_id, variant_id)
  where variant_id is not null;

create unique index IF not exists cart_items_dish_novariant_key
  on public.cart_items using btree (cart_id, food_item_id)
  where variant_id is null;


-- ── 4. Đơn hàng: snapshot tên biến thể ───────────────────────────────────────
alter table public.order_items
  add column if not exists variant_name_snapshot text null;

commit;


-- ── Kiểm tra sau khi chạy (read-only, chạy riêng ngoài transaction) ──────────
-- select column_name, data_type, is_nullable
--   from information_schema.columns
--  where table_schema = 'public'
--    and (table_name, column_name) in (
--          ('cart_items','variant_id'),
--          ('order_items','variant_name_snapshot'));
--
-- select indexname from pg_indexes
--  where schemaname = 'public' and tablename = 'cart_items';
--   -- expect: cart_items_pkey, cart_items_dish_variant_key,
--   --         cart_items_dish_novariant_key   (and NOT cart_items_cart_id_food_item_id_key)
--
-- select count(*) from public.food_item_variants;   -- expect 0 ngay sau migration