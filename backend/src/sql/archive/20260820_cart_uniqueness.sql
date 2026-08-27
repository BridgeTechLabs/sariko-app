-- Migration: uniqueness on carts / cart_items
--   carts(user_id)                   — one active cart per user
--   cart_items(cart_id, food_item_id) — one row per dish per cart
-- Without these, two concurrent POST /cart/add both read "no cart" and both insert.
-- The duplicate rows then break every singular read (.eq(user_id) + maybe_single),
-- which postgrest-py reports as the misleading "204 Missing response".
-- Run once against the live Supabase database.
--
-- Wrapped in a transaction on purpose: the DELETEs below are destructive, so if
-- either ALTER fails they must roll back too. Never leave rows deleted without the
-- constraint that made deleting them worthwhile.
-- (If the SQL Editor already opened a transaction, `begin` just logs a warning.)

begin;

-- De-duplicate first: keep the oldest cart per user, drop the rest.
-- cart_items rows of the dropped carts go with them (FK is ON DELETE CASCADE).
delete from public.carts c
where exists (
  select 1 from public.carts keep
  where keep.user_id = c.user_id
    and (coalesce(keep.created_at, 'epoch'::timestamp), keep.id)
      < (coalesce(c.created_at, 'epoch'::timestamp), c.id)
);

-- Same for duplicated dishes inside one cart: sum the quantities onto the survivor.
-- The survivor is "the row with no smaller id" — the exact negation of the DELETE
-- below, so the two statements cannot disagree on which row that is.
-- (Deliberately not min(id): aggregating uuid needs PG 14+ and the server version
-- could not be verified from here.)
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

alter table public.carts
  add constraint carts_user_id_key unique (user_id);

alter table public.cart_items
  add constraint cart_items_cart_id_food_item_id_key unique (cart_id, food_item_id);

commit;
