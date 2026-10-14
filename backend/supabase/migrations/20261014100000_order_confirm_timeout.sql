-- ============================================================
-- Refund on seller cancel + auto-cancel when the seller doesn't confirm in time
-- (TODO T2, T3). The window is admin_settings.order_confirm_minutes (30).
-- Expand-only: the running backend reads none of these columns and writes none
-- of these reasons, so it keeps working between this migration and the deploy.
-- ============================================================

-- 1. New refund reasons: the seller cancelled, or never confirmed in time.
alter table public.refunds drop constraint if exists refunds_reason_check;
alter table public.refunds add constraint refunds_reason_check check (
  reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text, 'seller_cancel'::text, 'seller_timeout'::text])
);

-- 2. One refund per order (refunds are always full), so two cancels racing
--    each other (seller vs the timeout job vs the buyer) cannot refund twice.
create unique index if not exists refunds_order_id_key on public.refunds (order_id);

-- 3. When the order was paid: the confirm clock starts here.
alter table public.orders add column if not exists paid_at timestamptz;

-- Orders already waiting for the seller get a fresh window from this deploy.
update public.orders
   set paid_at = now()
 where status = 'pending' and payment_status = 'paid' and paid_at is null;

create or replace function update_order_payment_status(
  p_order_id uuid,
  p_status text,
  p_transaction_ref text default null
) returns void as
$$
begin
  update public.orders
  set payment_status = p_status,
      paid_at = case when p_status = 'paid' then coalesce(paid_at, now()) else paid_at end
  where id = p_order_id;

  if p_transaction_ref is not null then
    update public.payments
    set status = p_status, transaction_ref = p_transaction_ref
    where order_id = p_order_id;
  end if;
end;
$$
language plpgsql security definer
set search_path = public;

-- 4. When the seller last switched the store open: an order paid while the store
--    was switched off gets its window from the moment it reopens.
--    A NULL is_open counts as open (column default), same as core/store_hours.py.
alter table public.seller_profiles add column if not exists opened_at timestamptz;

create or replace function public.set_seller_opened_at() returns trigger
  language plpgsql
  set search_path = public
as $$
begin
  if old.is_open is false and new.is_open is distinct from false then
    new.opened_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists on_seller_profiles_open on public.seller_profiles;
create trigger on_seller_profiles_open
  before update of is_open on public.seller_profiles
  for each row execute function public.set_seller_opened_at();

-- 5. Platform settings an admin can change without a deploy (key -> jsonb value).
--    The backend reads order_confirm_minutes on every expiry run (once a minute)
--    and falls back to 30 if the row is missing or not a positive integer.
create table if not exists public.admin_settings (
  key         text        not null,
  value       jsonb       not null,
  description text,
  updated_at  timestamptz not null default now(),
  constraint admin_settings_pkey primary key (key)
);

-- Backend-only (service role). Prod turns RLS on by itself via ensure_rls,
-- dev and fresh projects don't, so say it here.
alter table public.admin_settings enable row level security;

comment on table public.admin_settings is
  'Platform-wide settings. Adjustable by admin; the backend reads them at runtime.';

insert into public.admin_settings (key, value, description)
values ('order_confirm_minutes', '30'::jsonb,
        'Minutes (integer > 0) a seller has, during opening hours, to accept or reject a paid order before it is auto-cancelled and refunded.')
on conflict (key) do nothing;
