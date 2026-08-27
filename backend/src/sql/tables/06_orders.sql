-- ============================================================
-- Orders + order items (snapshot)
-- Commission + VAT are snapshotted at creation and never change after insert.
-- payout_amount = subtotal - commission_amount - vat_amount (delivery fee excluded).
-- ============================================================

create table public.orders (
  id uuid not null default gen_random_uuid (),
  user_id uuid null,
  seller_id uuid null,
  status text null default 'pending'::text,
  total_amount numeric not null,
  delivery_fee numeric null default 0,
  payment_status text null default 'pending'::text,
  delivery_method text null,
  delivery_address text null,
  note text null,
  created_at timestamp without time zone null default now(),
  delivery_lat double precision null,
  delivery_lon double precision null,
  quotation_id text null,
  cancellation_reason text null,
  transaction_ref text null,
  seller_user_id uuid null,
  subtotal numeric not null default 0,
  commission_rate numeric not null default 0,   -- snapshot from seller tier
  commission_amount numeric not null default 0,
  payout_amount numeric not null default 0,
  payout_status text not null default 'pending'::text,
  payout_id uuid null,
  vat_rate numeric not null default 0,           -- snapshot from admin_tax_config
  vat_amount numeric not null default 0,
  ipn_data jsonb null,
  delivery_appointment timestamp with time zone null,
  payment_create_date text null,
  constraint orders_pkey primary key (id),
  constraint orders_payout_id_fkey foreign KEY (payout_id) references admin_payouts (id) on delete set null,
  constraint orders_user_id_fkey foreign KEY (user_id) references users (id),
  constraint orders_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id),
  constraint orders_payment_status_check check (
    (payment_status = any (array['pending'::text, 'paid'::text, 'failed'::text]))
  ),
  constraint orders_delivery_method_check check (
    (delivery_method = any (array['pickup'::text, 'delivery'::text]))
  ),
  constraint orders_status_check check (
    (status = any (
      array[
        'pending'::text, 'confirmed'::text, 'ready'::text,
        'done'::text, 'cancelled'::text, 'delivery_failed'::text
      ]
    ))
  ),
  constraint orders_payout_status_check check (
    (payout_status = any (array['pending'::text, 'processing'::text, 'paid_out'::text]))
  )
) TABLESPACE pg_default;

create index IF not exists idx_orders_user on public.orders using btree (user_id) TABLESPACE pg_default;
create index IF not exists idx_orders_seller on public.orders using btree (seller_id) TABLESPACE pg_default;


create table public.order_items (
  id uuid not null default gen_random_uuid (),
  order_id uuid null,
  food_item_id uuid null,
  name_snapshot text null,
  price_snapshot numeric null,
  unit_label_snapshot text null,
  variant_name_snapshot text null,
  quantity integer not null,
  constraint order_items_pkey primary key (id),
  constraint order_items_food_item_id_fkey foreign KEY (food_item_id) references food_items (id),
  constraint order_items_order_id_fkey foreign KEY (order_id) references orders (id) on delete CASCADE
) TABLESPACE pg_default;

-- Every order detail read embeds order_items, and that page polls every 10s.
create index IF not exists idx_order_items_order on public.order_items using btree (order_id) TABLESPACE pg_default;

comment on column public.order_items.variant_name_snapshot is
  'Variant name at order time — "L", "4 người". Display and reconciliation only:
   price_snapshot already carries the FINAL unit price of that variant, so all
   existing price_snapshot * quantity arithmetic is unchanged.
   Deliberately no variant_id FK — a snapshot must never block a seller from
   deleting a variant, and nothing joins back to the variant row.';
