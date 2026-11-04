-- ============================================================
-- Daily portions per dish (T134, spec docs/dev/daily-portions Q1-Q5).
--   * food_items.daily_portions: portions the seller cooks per day (null = no limit, as before).
--     A day is the delivery day in Vietnam time: the delivery_appointment day (pre-order), else the
--     payment day. No reset job: a new day has no holds yet.
--   * order_portion_holds: the portions a paid order took. Sold on a day = sum(qty) of its holds.
--   * reserve_order_portions(order): all-or-nothing, at payment (the backend calls it before marking the
--     order paid). Locks the limited dishes FOR UPDATE in id order, so two buyers paying for the last
--     portion queue and the second one gets false (the backend then cancels + refunds, reason sold_out).
--   * Cancelling from pending / confirmed gives the portions back (trigger: every cancel path);
--     from ready / delivery_failed the food is cooked, the portions stay used.
-- ============================================================

alter table public.food_items add column if not exists daily_portions integer
  constraint food_items_daily_portions_check check (daily_portions is null or daily_portions > 0);

create table if not exists public.order_portion_holds (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  food_item_id uuid not null references public.food_items (id) on delete cascade,
  sale_date date not null,
  qty integer not null check (qty > 0),
  created_at timestamptz not null default now(),
  unique (order_id, food_item_id)
);
create index if not exists idx_order_portion_holds_food_date on public.order_portion_holds (food_item_id, sale_date);
alter table public.order_portion_holds enable row level security;   -- backend (service role) only

-- Portions left on p_sale_date for the limited dishes among p_food_item_ids (dishes without a limit are left out).
create or replace function public.portions_left(p_food_item_ids uuid[], p_sale_date date)
returns table (food_item_id uuid, daily_portions integer, remaining integer)
language sql stable security definer set search_path = public as
$$
  select f.id, f.daily_portions,
         greatest(f.daily_portions - coalesce((select sum(h.qty) from order_portion_holds h
                                                where h.food_item_id = f.id and h.sale_date = p_sale_date), 0), 0)::integer
    from food_items f
   where f.id = any (p_food_item_ids) and f.daily_portions is not null;
$$;

create or replace function public.reserve_order_portions(p_order_id uuid)
returns boolean
language plpgsql security definer set search_path = public as
$$
declare
  v_date date;
  r record;
begin
  select (coalesce(delivery_appointment, paid_at, now()) at time zone 'Asia/Ho_Chi_Minh')::date
    into v_date from orders where id = p_order_id;

  -- The limited dishes of the order, locked in id order (no deadlock between two orders).
  perform 1 from food_items
   where daily_portions is not null
     and id in (select food_item_id from order_items where order_id = p_order_id)
   order by id
     for update;

  -- After the lock: a retried IPN (or the reconcile job racing it) finds the holds already taken.
  if exists (select 1 from order_portion_holds where order_id = p_order_id) then
    return true;
  end if;

  for r in
    select f.daily_portions, sum(oi.quantity) as qty,
           coalesce((select sum(h.qty) from order_portion_holds h
                      where h.food_item_id = f.id and h.sale_date = v_date), 0) as used
      from order_items oi join food_items f on f.id = oi.food_item_id
     where oi.order_id = p_order_id and f.daily_portions is not null
     group by f.id, f.daily_portions
  loop
    if r.used + r.qty > r.daily_portions then
      return false;
    end if;
  end loop;

  insert into order_portion_holds (order_id, food_item_id, sale_date, qty)
  select p_order_id, oi.food_item_id, v_date, sum(oi.quantity)
    from order_items oi join food_items f on f.id = oi.food_item_id
   where oi.order_id = p_order_id and f.daily_portions is not null
   group by oi.food_item_id;
  return true;
end;
$$;

create or replace function public.release_order_portions()
returns trigger
language plpgsql security definer set search_path = public as
$$
begin
  delete from order_portion_holds where order_id = new.id;
  return new;
end;
$$;

drop trigger if exists trg_release_order_portions on public.orders;
create trigger trg_release_order_portions
  after update of status on public.orders
  for each row
  when (new.status = 'cancelled' and old.status in ('pending', 'confirmed'))
  execute function public.release_order_portions();

revoke execute on function public.portions_left(uuid[], date), public.reserve_order_portions(uuid)
  from public, anon, authenticated;
grant execute on function public.portions_left(uuid[], date), public.reserve_order_portions(uuid) to service_role;

-- A paid order cancelled because its last portion went while the buyer paid.
alter table public.refunds drop constraint if exists refunds_reason_check;
alter table public.refunds add constraint refunds_reason_check check (
  reason = any (array['buyer_cancel'::text, 'driver_booking_failed'::text, 'seller_cancel'::text,
                      'seller_timeout'::text, 'admin_cancel'::text, 'late_payment'::text,
                      'duplicate_payment'::text, 'sold_out'::text])
);
