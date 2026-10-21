-- ============================================================
-- A seller can delete a dish / price level that has been ordered (spec docs/dev/menu-delete, T87).
-- These FKs had no ON DELETE, so deleting a dish that was ever ordered or sits in a cart
-- failed with 23503 (API 500).
--   * order_items: SET NULL. The order keeps name_snapshot / price_snapshot /
--     variant_name_snapshot; the dish content itself is in history_menu.
--   * cart_items (dish and price level): CASCADE. The cart line goes, the cart stays valid.
-- Constraint names checked against reference/schema_dev.sql and schema_prod.sql.
-- ============================================================
alter table public.order_items drop constraint if exists order_items_food_item_id_fkey;
alter table public.order_items add constraint order_items_food_item_id_fkey
  foreign key (food_item_id) references public.food_items (id) on delete set null;

alter table public.cart_items drop constraint if exists cart_items_food_item_id_fkey;
alter table public.cart_items add constraint cart_items_food_item_id_fkey
  foreign key (food_item_id) references public.food_items (id) on delete cascade;

alter table public.cart_items drop constraint if exists cart_items_variant_id_fkey;
alter table public.cart_items add constraint cart_items_variant_id_fkey
  foreign key (variant_id) references public.food_item_variants (id) on delete cascade;
