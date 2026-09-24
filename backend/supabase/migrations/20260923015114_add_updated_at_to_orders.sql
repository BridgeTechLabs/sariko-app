-- ============================================================
-- orders.updated_at — polling probe support
-- The order-list pollers hit /orders/head and /sellers/me/orders/head first
-- (max(updated_at) + row count) and only refetch the full list when that
-- signature moves, so an idle tick costs one index read instead of a joined
-- query over the whole order history.
-- ============================================================

alter table public.orders
  add column if not exists updated_at timestamp with time zone not null default now();

create index if not exists idx_orders_user_updated
  on public.orders using btree (user_id, updated_at desc);
create index if not exists idx_orders_seller_updated
  on public.orders using btree (seller_id, updated_at desc);

create or replace function public.set_orders_updated_at () returns trigger
  language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_orders_update on public.orders;
create trigger on_orders_update
  before update on public.orders
  for each row
  execute function public.set_orders_updated_at ();
