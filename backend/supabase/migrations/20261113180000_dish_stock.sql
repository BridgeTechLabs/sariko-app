-- ============================================================
-- Dish stock (seller-menu đợt 2 S1, ADR 0004 option A, QĐ2-1..QĐ2-6, QĐ2-10): "portions per day" becomes
-- one number per dish, the portions it can still sell.
--   * food_items.stock: null = no limit. Paid orders take from it (reserve_order_stock, at payment, as before),
--     a cancel from pending / confirmed gives back, the seller's save overwrites it. No daily reset.
--   * order_portion_holds stays the book of "which paid order took how much" so a cancel gives back once;
--     sale_date no longer means anything (dropped with daily_portions in a later migration).
--   * reserve_order_stock returns the dishes that just went below their minimum per order (the seller gets one
--     push each, at most one per dish every stock_alert_cooldown_minutes), [] when nothing did, null when a
--     dish is short (nothing taken).
--   * The old backend runs a few minutes against this schema while deploying: reserve_order_portions and
--     portions_left keep their signatures and read the stock. daily_portions stays until that migration.
-- ============================================================

alter table public.food_items add column if not exists stock integer
  constraint food_items_stock_check check (stock is null or stock between 0 and 100000);   -- input bound, not a business cap
alter table public.food_items add column if not exists stock_alert_at timestamptz;   -- last out-of-stock push for the dish

-- QĐ2-6: a paid order writes stock (and stock_alert_at) on the dish; that is not a seller edit, so no menu history
-- row. Was: rating_avg / rating_count only (20261016040000_history_menu_rename.sql, same body on DEV + PROD).
create or replace function public.log_history_menu()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- on_review_change rewrites food_items.rating_* on every review; paid orders and cancels move stock: not seller edits.
  if tg_op = 'UPDATE'
     and (to_jsonb(old) - 'rating_avg' - 'rating_count' - 'stock' - 'stock_alert_at')
       = (to_jsonb(new) - 'rating_avg' - 'rating_count' - 'stock' - 'stock_alert_at') then
    return null;
  end if;
  insert into public.history_menu (table_name, row_id, op, old_row)
  values (tg_table_name, old.id, tg_op, to_jsonb(old));
  return null;
end;
$$;

-- QĐ2-5: a dish with N a day starts with what is left of today and later days (pre-orders already paid);
-- holds of past days are gone from the book (their sales stay in order_items), so a late cancel adds nothing back.
update public.food_items f
   set stock = least(greatest(f.daily_portions - coalesce(
         (select sum(h.qty) from public.order_portion_holds h
           where h.food_item_id = f.id and h.sale_date >= (now() at time zone 'Asia/Ho_Chi_Minh')::date), 0), 0), 100000)
 where f.daily_portions is not null and f.stock is null;
delete from public.order_portion_holds where sale_date < (now() at time zone 'Asia/Ho_Chi_Minh')::date;

-- QĐ2-2: at payment. All or nothing, once per order. Locks the order's limited dishes FOR UPDATE in id order, so
-- two buyers paying for the last portion queue and the second gets null (the backend cancels + refunds, sold_out),
-- and a seller saving a new stock meanwhile waits for the lock.
create or replace function public.reserve_order_stock(p_order_id uuid, p_cooldown_minutes integer default 30)
returns jsonb
language plpgsql security definer set search_path = public as
$$
declare
  v_crossed jsonb;
  v_ids uuid[];
begin
  perform 1 from food_items
   where stock is not null
     and id in (select food_item_id from order_items where order_id = p_order_id)
   order by id
     for update;

  -- TODO (BM15): an IPN landing while the buyer cancels the pending order still takes stock (the cancel already
  -- ran, nothing gives it back); a narrow window, healed by the seller's next count.
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

  insert into order_portion_holds (order_id, food_item_id, sale_date, qty)
  select p_order_id, oi.food_item_id, (now() at time zone 'Asia/Ho_Chi_Minh')::date, sum(oi.quantity)
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

-- QĐ2-3: the old backend's two functions, same signatures, now on the stock.
create or replace function public.reserve_order_portions(p_order_id uuid)
returns boolean
language plpgsql security definer set search_path = public as
$$
begin
  return public.reserve_order_stock(p_order_id) is not null;
end;
$$;

create or replace function public.portions_left(p_food_item_ids uuid[], p_sale_date date)
returns table (food_item_id uuid, daily_portions integer, remaining integer)
language sql stable security definer set search_path = public as
$$
  select f.id, f.daily_portions, f.stock
    from food_items f
   where f.id = any (p_food_item_ids) and f.stock is not null;
$$;

-- QĐ2-4: a cancel from pending / confirmed (trigger condition unchanged) gives the order's portions back once: the
-- holds are deleted and exactly what was deleted is added. A dish whose limit the seller removed stays null;
-- the CHECK bound is never passed, so the cancel (and its refund) never fails on it. Dishes locked in id order,
-- as reserve_order_stock does, so a cancel and a payment on the same dishes can't deadlock.
create or replace function public.release_order_portions()
returns trigger
language plpgsql security definer set search_path = public as
$$
begin
  perform 1 from food_items
   where stock is not null
     and id in (select food_item_id from order_portion_holds where order_id = new.id)
   order by id
     for update;
  with released as (
    delete from order_portion_holds where order_id = new.id returning food_item_id, qty
  )
  update food_items f
     set stock = least(f.stock + r.qty, 100000)
    from released r
   where f.id = r.food_item_id and f.stock is not null;
  return new;
end;
$$;

-- BM14: the new function is the backend's only (service role); the replaced ones keep their grants (create or replace).
revoke execute on function public.reserve_order_stock(uuid, integer) from public, anon, authenticated;
grant execute on function public.reserve_order_stock(uuid, integer) to service_role;

insert into public.admin_settings (key, value, description)
values ('stock_alert_cooldown_minutes', '30'::jsonb,
        'Minutes before the same dish can send another out-of-stock push to its seller')
on conflict (key) do nothing;
