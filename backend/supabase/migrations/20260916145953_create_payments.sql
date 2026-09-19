-- ============================================================
-- Payments (VNPay charge / refund records)
-- ============================================================

create table if not exists public.payments (
  id uuid not null default gen_random_uuid (),
  order_id uuid null,
  method text null,
  amount numeric null,
  status text null,
  transaction_ref text null,
  created_at timestamp without time zone null default now(),
  type text not null default 'charge'::text,
  vnp_transaction_no text null,
  refund_id uuid null,
  constraint payments_pkey primary key (id),
  constraint payments_order_id_fkey foreign KEY (order_id) references orders (id) on delete CASCADE,
  constraint payments_refund_id_fkey foreign KEY (refund_id) references refunds (id) on delete set null,
  constraint payments_type_check check (
    (type = any (array['charge'::text, 'refund'::text]))
  )
) TABLESPACE pg_default;
