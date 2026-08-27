-- ============================================================
-- Carts + cart items (one active cart per user, single-seller)
-- ============================================================

create table public.carts (
  id uuid not null default gen_random_uuid (),
  user_id uuid null,
  seller_id uuid null,
  created_at timestamp without time zone null default now(),
  constraint carts_pkey primary key (id),
  constraint carts_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id),
  constraint carts_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE,
  -- One active cart per user. Without this, two concurrent /cart/add requests both
  -- read "no cart" and both insert, and every later .eq(user_id) singular read breaks.
  constraint carts_user_id_key unique (user_id)
) TABLESPACE pg_default;


create table public.cart_items (
  id uuid not null default gen_random_uuid (),
  cart_id uuid null,
  food_item_id uuid null,
  variant_id uuid null,
  quantity integer not null,
  constraint cart_items_pkey primary key (id),
  constraint cart_items_cart_id_fkey foreign KEY (cart_id) references carts (id) on delete CASCADE,
  constraint cart_items_food_item_id_fkey foreign KEY (food_item_id) references food_items (id),
  -- No ON DELETE, same as the food_items FK: a variant sitting in someone's cart
  -- must not vanish underneath them. Retire levels with is_available instead.
  constraint cart_items_variant_id_fkey foreign KEY (variant_id) references food_item_variants (id),
  constraint cart_items_quantity_check check ((quantity > 0))
) TABLESPACE pg_default;

-- One row per (cart, dish, level); quantity carries the count. Same race as carts.
-- Two PARTIAL indexes rather than one `unique nulls not distinct (...)`: that form
-- needs PG 15+ and the server version could not be verified from the dev machine
-- (see archive/20260820_cart_uniqueness.sql). These work on every version and say
-- the intent plainly — with a level, unique per level; without one, unique per dish.
create unique index IF not exists cart_items_dish_variant_key
  on public.cart_items using btree (cart_id, food_item_id, variant_id)
  where variant_id is not null;

create unique index IF not exists cart_items_dish_novariant_key
  on public.cart_items using btree (cart_id, food_item_id)
  where variant_id is null;

comment on column public.cart_items.variant_id is
  'NULL for dishes without variants. The cart holds a REFERENCE, never a snapshot:
   the unit price is read live from food_item_variants.price (or food_items.price
   when NULL) on every cart read, so a seller price change is reflected at once.';
