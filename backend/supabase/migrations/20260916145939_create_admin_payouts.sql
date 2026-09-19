-- ============================================================
-- Admin payout batches — one row per weekly payout run per seller.
-- Created BEFORE orders because orders.payout_id references it.
-- ============================================================

create table if not exists public.admin_payouts (
  id                 uuid        not null default gen_random_uuid(),
  seller_id          uuid        not null,  -- FK → seller_profiles.id
  period_start       date        not null,
  period_end         date        not null,
  order_count        integer     not null default 0,
  total_subtotal     numeric     not null default 0,
  total_commission   numeric     not null default 0,
  total_vat          numeric     not null default 0,
  gross_payout       numeric     not null default 0,  -- subtotal - commission - vat
  withholding_rate   numeric     not null default 0,  -- snapshot at payout time
  withholding_amount numeric     not null default 0,
  net_payout         numeric     not null default 0,  -- gross_payout - withholding
  status             text        not null default 'pending'
    constraint admin_payouts_status_check check (
      status = any (array['pending', 'processing', 'completed', 'failed'])
    ),
  note               text,
  paid_at            timestamptz,
  created_at         timestamptz not null default now(),
  constraint admin_payouts_pkey primary key (id),
  constraint admin_payouts_seller_id_fkey foreign KEY (seller_id) references public.seller_profiles (id)
);

create index IF not exists idx_admin_payouts_seller_id on public.admin_payouts (seller_id);
create index IF not exists idx_admin_payouts_status on public.admin_payouts (status);

comment on table public.admin_payouts is
  'Weekly payout batch per seller. One row = one bank transfer to seller.';
