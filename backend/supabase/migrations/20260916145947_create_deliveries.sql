-- ============================================================
-- Deliveries (Lalamove booking + driver tracking, per order)
-- ============================================================

create table if not exists public.deliveries (
  id uuid not null default gen_random_uuid (),
  order_id uuid null,
  provider text null,
  status text null,
  tracking_url text null,
  driver_name text null,
  driver_phone text null,
  created_at timestamp without time zone null default now(),
  estimated_pickup_time timestamp without time zone null,
  share_link text null,
  driver_plate text null,
  lalamove_order_id text null,
  rebook_count integer null default 0,
  user_id uuid null,
  seller_user_id uuid null,
  constraint deliveries_pkey primary key (id),
  constraint deliveries_order_id_fkey foreign KEY (order_id) references orders (id) on delete CASCADE,
  constraint deliveries_seller_user_id_fkey foreign KEY (seller_user_id) references users (id),
  constraint deliveries_user_id_fkey foreign KEY (user_id) references users (id)
) TABLESPACE pg_default;

create index IF not exists idx_deliveries_order_id on public.deliveries using btree (order_id) TABLESPACE pg_default;
create index IF not exists idx_deliveries_lalamove_order_id on public.deliveries using btree (lalamove_order_id) TABLESPACE pg_default;
create index IF not exists idx_deliveries_user_id on public.deliveries using btree (user_id) TABLESPACE pg_default;
create index IF not exists idx_deliveries_seller_user_id on public.deliveries using btree (seller_user_id) TABLESPACE pg_default;
