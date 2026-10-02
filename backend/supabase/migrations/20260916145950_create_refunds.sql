-- ============================================================
-- Refunds (VNPay refund tracking) — created before payments (payments.refund_id FK).
-- ============================================================

create table if not exists public.refunds (
  id uuid not null default gen_random_uuid (),
  order_id uuid not null,
  amount numeric not null,
  reason text not null,
  status text not null default 'pending'::text,
  original_txn_ref text null,
  ipn_data jsonb null,
  vnpay_refund_ref text null,
  created_at timestamp with time zone null default now(),
  processed_at timestamp with time zone null,
  note text null,
  payment_create_date text null,
  constraint refunds_pkey primary key (id),
  constraint refunds_order_id_fkey foreign KEY (order_id) references orders (id),
  constraint refunds_reason_check check (
    (reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text]))
  ),
  constraint refunds_status_check check (
    (status = any (array['pending'::text, 'processed'::text, 'failed'::text]))
  )
) TABLESPACE pg_default;
