-- ============================================================
-- Reviews (buyer rates a completed order)
-- One submit writes 1 + N rows, distinguished by food_item_id:
--   food_item_id IS NULL     → the order's overall rating  → seller_profiles.rating_avg
--   food_item_id IS NOT NULL → a per-dish rating           → food_items.rating_avg
-- Overall rows carry no comment by design; per-dish comments are optional.
-- ============================================================

create table if not exists public.reviews (
  id uuid not null default gen_random_uuid (),
  order_id uuid null,
  seller_id uuid null,
  user_id uuid null,
  food_item_id uuid null,
  rating integer null,
  comment text null,
  created_at timestamp without time zone null default now(),
  constraint reviews_pkey primary key (id),
  constraint reviews_order_id_fkey foreign KEY (order_id) references orders (id) on delete CASCADE,
  constraint reviews_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id),
  constraint reviews_user_id_fkey foreign KEY (user_id) references users (id),
  constraint reviews_food_item_id_fkey foreign KEY (food_item_id) references food_items (id) on delete CASCADE,
  constraint reviews_rating_check check (((rating >= 1) and (rating <= 5)))
) TABLESPACE pg_default;

-- Uniqueness is split in two on purpose: Postgres treats every NULL as distinct, so a
-- plain unique (order_id, food_item_id) would happily accept two overall rows per order.
create unique index if not exists uniq_review_order_item
  on public.reviews (order_id, food_item_id)
  where food_item_id is not null;

create unique index if not exists uniq_review_order_overall
  on public.reviews (order_id)
  where food_item_id is null;

-- order_id is the hottest lookup (orders-list embed, order detail, review submit) and
-- Postgres does not index FK columns automatically. The two partial unique indexes
-- above cannot serve a bare order_id = ? lookup: each covers only half the rows.
create index if not exists idx_reviews_order on public.reviews using btree (order_id) TABLESPACE pg_default;
create index if not exists idx_reviews_food_item on public.reviews using btree (food_item_id) TABLESPACE pg_default;
create index if not exists idx_reviews_seller on public.reviews using btree (seller_id) TABLESPACE pg_default;
