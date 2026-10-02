-- ============================================================
-- Menu: categories + food items (both scoped to a seller_profile)
-- ============================================================

create table if not exists public.menu_categories (
  id uuid not null default gen_random_uuid (),
  seller_id uuid null,
  name text not null,
  sort_order integer null default 0,
  is_active boolean null default true,
  created_at timestamp without time zone null default now(),
  updated_at timestamp without time zone null default now(),
  constraint menu_categories_pkey primary key (id),
  constraint menu_categories_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id) on delete CASCADE
) TABLESPACE pg_default;


create table if not exists public.food_items (
  id uuid not null default gen_random_uuid (),
  seller_id uuid null,
  category_id uuid null,
  name text not null,
  description text null,
  price numeric not null,
  unit_label text null,
  min_quantity integer null default 1,
  quantity_step integer null default 1,
  preorder_day integer null default 0,
  is_available boolean null default true,
  image_url text null,
  created_at timestamp without time zone null default now(),
  price_text text null,
  is_featured boolean not null default false,
  rating_avg numeric null,
  rating_count integer not null default 0,
  constraint food_items_pkey primary key (id),
  constraint food_items_category_id_fkey foreign KEY (category_id) references menu_categories (id) on delete set null,
  constraint food_items_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_food_items_seller on public.food_items using btree (seller_id) TABLESPACE pg_default;

comment on column public.food_items.rating_avg is
  'Denormalised from reviews (per-dish rows only). Maintained by the on_review_change
   trigger — never write it by hand. NULL until the first review.';


-- ============================================================
-- Price variants: one required, single-select level per dish
-- (added 2026-08-24 — archive/20260824_food_item_variants.sql)
-- ============================================================

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
  constraint food_item_variants_food_item_id_fkey foreign KEY (food_item_id) references food_items (id) on delete CASCADE,
  -- The name is what the buyer picks by and what gets snapshotted onto the order.
  constraint food_item_variants_food_item_id_name_key unique (food_item_id, name),
  constraint food_item_variants_price_check check ((price >= (0)::numeric))
) TABLESPACE pg_default;

create index IF not exists idx_food_item_variants_item on public.food_item_variants using btree (food_item_id) TABLESPACE pg_default;

comment on table public.food_item_variants is
  'One row per selectable price level of a dish ("S"/"M"/"L", "1 người"/"4 người").
   Exactly one must be chosen when the dish has variants — this is not a topping /
   add-on model, nothing here is cumulative. There is deliberately NO group-label
   column on food_items: the presence of rows here is the single source of truth
   for "does this dish have levels?", and the UI heading is a translated string in
   the frontend rather than seller-typed text no locale file can reach.';

comment on column public.food_item_variants.price is
  'ABSOLUTE price of this level, NOT a delta on food_items.price. No code path adds
   the two together. This is what keeps order_items.price_snapshot meaning "final
   unit price paid", so every price_snapshot * quantity on the frontend stays valid.';

comment on column public.food_item_variants.price_text is
  'Display string derived from price by _make_price_text() in apis/sellers.py.
   Same contract as food_items.price_text — never write it by hand.';
