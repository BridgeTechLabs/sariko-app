-- ============================================================
-- When an order last changed status (TODO T80, T82). The buyer may cancel a
-- `confirmed` order 1 hour after it was confirmed, and a `delivery_failed`
-- order 30 minutes after the trip failed (docs/dev/order-cancel-refund.md R4, R6).
-- updated_at can't be used: the Lalamove webhook touches the row too.
-- Expand-only: the running backend never reads this column.
-- ============================================================

-- Existing rows get the migration time, so orders already waiting get a fresh
-- window from this deploy. New orders get their insert time.
alter table public.orders
  add column if not exists status_changed_at timestamptz not null default now();

create or replace function public.set_order_status_changed_at() returns trigger
  language plpgsql
  set search_path = public
as $$
begin
  if new.status is distinct from old.status then
    new.status_changed_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists on_orders_status_change on public.orders;
create trigger on_orders_status_change
  before update of status on public.orders
  for each row execute function public.set_order_status_changed_at();
