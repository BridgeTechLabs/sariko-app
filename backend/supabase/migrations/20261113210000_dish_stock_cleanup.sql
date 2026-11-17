-- ============================================================
-- Dish stock cleanup (seller-menu đợt 4A S3, T204 + T205; ADR 0004 HỆ QUẢ 2). Runs once PROD has the stock code
-- (5eeb461), which reads none of what is dropped here, so rolling the image back to it still works.
--   * T204: the old backend's wrappers reserve_order_portions / portions_left, order_portion_holds.sale_date (+ its
--     index) and food_items.daily_portions (+ its CHECK) go; the holds stay the book of "which paid order took how
--     much" (20261113180000_dish_stock.sql).
--   * T205 (BM15): reserve_order_stock locks the order row before the dishes and takes nothing from an order that is
--     no longer pending. A cancel locks the same row first (UPDATE orders, then its trigger locks the dishes), so
--     whichever comes second waits: cancel first -> nothing taken; payment first -> the cancel gives it back.
--     Same signature, so the grants of 20261113180000 stay (service_role only).
--   * T208: update_order_payment_status marks an order paid only while it is still pending, and says whether it did:
--     a cancel landing between the IPN's read and this write no longer leaves a cancelled order marked paid with no
--     refund; the backend sends that payment down the late_payment refund instead.
-- ============================================================

create or replace function public.reserve_order_stock(p_order_id uuid, p_cooldown_minutes integer default 30)
returns jsonb
language plpgsql security definer set search_path = public as
$$
declare
  v_status text;
  v_crossed jsonb;
  v_ids uuid[];
begin
  select status into v_status from orders where id = p_order_id for no key update;   -- what the cancel's UPDATE takes
  if v_status is distinct from 'pending' then
    return '[]'::jsonb;
  end if;

  -- The order's limited dishes, locked in id order (no deadlock between two orders).
  perform 1 from food_items
   where stock is not null
     and id in (select food_item_id from order_items where order_id = p_order_id)
   order by id
     for update;

  -- After the lock: a retried IPN (or the reconcile job racing it) finds the stock already taken.
  if exists (select 1 from order_portion_holds where order_id = p_order_id) then
    return '[]'::jsonb;
  end if;

  if exists (select 1 from order_items oi join food_items f on f.id = oi.food_item_id
              where oi.order_id = p_order_id and f.stock is not null
              group by f.id, f.stock
             having sum(oi.quantity) > f.stock) then
    return null;
  end if;

  insert into order_portion_holds (order_id, food_item_id, qty)
  select p_order_id, oi.food_item_id, sum(oi.quantity)
    from order_items oi join food_items f on f.id = oi.food_item_id
   where oi.order_id = p_order_id and f.stock is not null
   group by oi.food_item_id;

  -- The dishes that cross: at least their minimum per order before, less after. Listed (and stamped) only when their
  -- last push is older than the cooldown (BM13). Worked out from the values before the take, still under the lock.
  select coalesce(array_agg(f.id), '{}'),
         coalesce(jsonb_agg(jsonb_build_object('id', f.id, 'name', f.name, 'stock', f.stock - h.qty,
                                               'min_quantity', greatest(coalesce(f.min_quantity, 1), 1)) order by f.id), '[]'::jsonb)
    into v_ids, v_crossed
    from food_items f join order_portion_holds h on h.food_item_id = f.id and h.order_id = p_order_id
   where f.stock >= greatest(coalesce(f.min_quantity, 1), 1)
     and f.stock - h.qty < greatest(coalesce(f.min_quantity, 1), 1)
     and (f.stock_alert_at is null or f.stock_alert_at < now() - make_interval(mins => p_cooldown_minutes));

  update food_items f
     set stock = f.stock - h.qty,
         stock_alert_at = case when f.id = any (v_ids) then now() else f.stock_alert_at end
    from order_portion_holds h
   where h.order_id = p_order_id and h.food_item_id = f.id;
  return v_crossed;
end;
$$;

drop function if exists public.reserve_order_portions(uuid);
drop function if exists public.portions_left(uuid[], date);
drop index if exists public.idx_order_portion_holds_food_date;
alter table public.order_portion_holds drop column if exists sale_date;
alter table public.food_items drop column if exists daily_portions;   -- its CHECK goes with it

-- T208: was "where id = p_order_id" (20261110200000_audit_logic.sql). Returns "the order still waits" (status pending),
-- not "something changed": a paid order stays pending until the seller takes it, so a repeated IPN / reconcile of a
-- rightly paid order is never refunded. Only 'paid' asks for it; the DEV panel's "pending" (force-status) writes as
-- before. The return type changes (void -> boolean): drop + create, and the grants are set again below for every
-- overload. PROD also had a 2-argument one made by hand ("where id" only, the same T208 flaw, no caller): dropped.
-- Callers: dao_orders.update_payment_status only (app + admin grep, pg_proc).
drop function if exists public.update_order_payment_status(uuid, text);   -- made by hand on PROD, same flaw, nobody calls it
drop function public.update_order_payment_status(uuid, text, text);
create function public.update_order_payment_status(
  p_order_id uuid,
  p_status text,
  p_transaction_ref text default null
) returns boolean
language plpgsql security definer
set search_path = public as
$$
begin
  update public.orders
     set payment_status = p_status,
         paid_at = case when p_status = 'paid' then coalesce(paid_at, now()) else paid_at end,
         transaction_ref = coalesce(p_transaction_ref, transaction_ref)
   where id = p_order_id and (p_status <> 'paid' or status = 'pending');
  if not found then
    return false;
  end if;

  if p_transaction_ref is not null then
    update public.payments
       set status = case when p_status = 'paid' then 'succeeded' else p_status end
     where order_id = p_order_id and type = 'charge' and transaction_ref = p_transaction_ref;
  end if;
  return true;
end;
$$;
do $$
declare
  f regprocedure;
begin
  for f in
    select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'update_order_payment_status'
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;
