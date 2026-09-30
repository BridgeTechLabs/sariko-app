-- ============================================================
-- Indexes for the columns the app actually filters / joins on.
-- Only what is missing: every index already declared in sql/tables/* is skipped
-- (orders user/seller + *_updated, order_items.order_id, reviews.order/food_item/seller,
--  deliveries.*, food_items.seller_id, food_item_variants.food_item_id,
--  chat_conversations.buyer/seller, chat_messages.conversation, admin_payouts.*,
--  seller_profiles.slug + lat/lon, carts.user_id, cart_items unique partials).
--
-- Plain CREATE INDEX (not CONCURRENTLY): supabase migrations run inside a
-- transaction, and these tables are small enough that the lock is momentary.
-- ============================================================


-- ── seller_profiles.user_id ─────────────────────────────────────────────────
-- The single hottest unindexed column. Read on every seller request
-- (read_seller_profile_by_user_id, update_seller_profile_info, update_avatar_url)
-- AND re-evaluated by four RLS policies that all run
-- `seller_id in (select id from seller_profiles where user_id = auth.uid())`
-- (menu_categories, food_items, food_item_variants, orders).
create index if not exists idx_seller_profiles_user
  on public.seller_profiles using btree (user_id);


-- ── menu_categories.seller_id ───────────────────────────────────────────────
-- Entry point of the whole storefront menu read: read_food_items_by_seller_id /
-- read_menu_by_seller_id start from menu_categories.eq(seller_id) and embed
-- food_items from there. Also the FK target of the seller_profiles cascade.
create index if not exists idx_menu_categories_seller
  on public.menu_categories using btree (seller_id);


-- ── food_items.category_id ──────────────────────────────────────────────────
-- PostgREST resolves the `menu_categories → food_items(...)` embed above as
-- `food_items.category_id in (...)`, so the menu read needs this too.
create index if not exists idx_food_items_category
  on public.food_items using btree (category_id);


-- ── payments.order_id ───────────────────────────────────────────────────────
-- update_order_payment_status() does `update payments where order_id = ?` on
-- every VNPay IPN. Unindexed FK also makes the orders ON DELETE CASCADE scan.
create index if not exists idx_payments_order
  on public.payments using btree (order_id);


-- ── refunds.order_id ────────────────────────────────────────────────────────
-- `refunds(status)` is embedded in both read_orders_by_user_id and
-- read_order_by_id — i.e. on the order list (15s poll) and order detail (10s poll).
create index if not exists idx_refunds_order
  on public.refunds using btree (order_id);


-- ── user_addresses.user_id ──────────────────────────────────────────────────
-- read_default_address runs on every auth bootstrap; upsert_default_address
-- re-reads the same filter before writing.
create index if not exists idx_user_addresses_user
  on public.user_addresses using btree (user_id);


-- ── order_items.food_item_id / cart_items.food_item_id / cart_items.variant_id ──
-- These three FKs have no ON DELETE, so Postgres must scan the child table every
-- time a seller deletes a dish or a variant from the menu editor. Without an
-- index that is a full seq scan of order_items, which only ever grows.
create index if not exists idx_order_items_food_item
  on public.order_items using btree (food_item_id);

create index if not exists idx_cart_items_food_item
  on public.cart_items using btree (food_item_id);

create index if not exists idx_cart_items_variant
  on public.cart_items using btree (variant_id);


-- ── orders: seller list ─────────────────────────────────────────────────────
-- read_orders_by_seller_id = eq(seller_id) + eq(payment_status,'paid') + order by
-- created_at desc. idx_orders_seller gets the seller but leaves the filter and the
-- sort; this partial composite answers the whole thing. Partial because the seller
-- dashboard never looks at unpaid orders.
create index if not exists idx_orders_seller_paid_created
  on public.orders using btree (seller_id, created_at desc)
  where payment_status = 'paid';


-- ── food_items: featured dishes (home page, anonymous traffic) ──────────────
-- read_featured_dishes = eq(is_featured,true) + eq(is_available,true), limit 12.
-- Partial index so it stays tiny however large the menu grows.
create index if not exists idx_food_items_featured
  on public.food_items using btree (seller_id)
  where is_featured and is_available;


-- ── chat_messages: unread badge ─────────────────────────────────────────────
-- read_unread_rows = in_(conversation_id) + read_at is null, on every
-- conversation-list load. idx_chat_messages_conversation is sorted by created_at
-- and covers the whole history; this one only ever holds the unread tail.
create index if not exists idx_chat_messages_unread
  on public.chat_messages using btree (conversation_id)
  where read_at is null;


-- ── search: ILIKE '%q%' on names ────────────────────────────────────────────
-- GET /search does `ilike('%q%')` on food_items.name and menu_categories.name.
-- A leading wildcard cannot use a btree index at all — trigram GIN is the only
-- thing that helps here. pg_trgm ships with Supabase.
create extension if not exists pg_trgm;

create index if not exists idx_food_items_name_trgm
  on public.food_items using gin (name gin_trgm_ops);

create index if not exists idx_menu_categories_name_trgm
  on public.menu_categories using gin (name gin_trgm_ops);
