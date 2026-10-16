-- ============================================================
-- Order + delivery history (T84) for the admin order detail, used to settle
-- buyer/seller complaints: when each status was reached, and which driver
-- had the trip. orders.status_changed_at and deliveries keep only the latest
-- value, and the Lalamove webhook clears the driver fields when a trip ends
-- REJECTED/CANCELLED/EXPIRED — so both are copied here by triggers, whoever
-- writes (marketplace backend, admin repo, timeout job, webhook).
-- No FK to orders: history outlives a deleted order. Orders placed before
-- this migration have no rows; the admin detail falls back to created_at /
-- paid_at / status_changed_at for them.
-- Expand-only: the running backend never reads these tables.
-- ============================================================

create table if not exists public.history_order_status (
  id bigint generated always as identity,
  order_id uuid not null,
  status text not null,
  changed_at timestamp with time zone not null default now(),
  constraint history_order_status_pkey primary key (id)
);

create index if not exists history_order_status_order_idx on public.history_order_status (order_id);

create table if not exists public.history_delivery (
  id bigint generated always as identity,
  delivery_id uuid not null,
  order_id uuid,
  status text,
  driver_name text,
  driver_phone text,
  driver_plate text,
  changed_at timestamp with time zone not null default now(),
  constraint history_delivery_pkey primary key (id)
);

create index if not exists history_delivery_order_idx on public.history_delivery (order_id);

-- Backend-only tables (service_role bypasses RLS); no policies → anon/authenticated get nothing.
alter table public.history_order_status enable row level security;
alter table public.history_delivery enable row level security;

-- security definer: the history insert must not fail because the writer's role
-- has no policy on these tables.
create or replace function public.log_order_status()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into public.history_order_status (order_id, status) values (new.id, new.status);
  end if;
  return null;
end;
$$;

drop trigger if exists orders_status_history on public.orders;
create trigger orders_status_history after insert or update of status on public.orders
  for each row execute function public.log_order_status();

create or replace function public.log_delivery()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT'
     or new.status is distinct from old.status
     or new.driver_name is distinct from old.driver_name
     or new.driver_phone is distinct from old.driver_phone
     or new.driver_plate is distinct from old.driver_plate then
    insert into public.history_delivery (delivery_id, order_id, status, driver_name, driver_phone, driver_plate)
    values (new.id, new.order_id, new.status, new.driver_name, new.driver_phone, new.driver_plate);
  end if;
  return null;
end;
$$;

drop trigger if exists deliveries_history on public.deliveries;
create trigger deliveries_history after insert or update on public.deliveries
  for each row execute function public.log_delivery();
