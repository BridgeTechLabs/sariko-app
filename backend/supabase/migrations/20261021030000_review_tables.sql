-- ============================================================
-- Reviews split into two tables (spec docs/dev/menu-delete, group B; replaces public.reviews).
-- reviews mixed both kinds in one table, "food_item_id is null" meaning the store rating, so
-- a dish review could not outlive its dish (T87). Now:
--   * review_stores: the store rating, one per order, required, with an optional comment.
--   * review_items: optional dish ratings. food_item_id ON DELETE SET NULL + name_snapshot,
--     so a deleted dish keeps its reviews under the name it had.
-- Ratings: seller_profiles.rating_* from review_stores only, food_items.rating_* from
-- review_items only, recalculated from scratch by row triggers (as before).
-- Existing rows are moved over (ids kept), then reviews and its function are dropped.
-- Between this db push and the backend deploy the old backend still calls reviews and
-- fails (pre go-live, accepted).
-- ============================================================

create table if not exists public.review_stores (
  id uuid not null default gen_random_uuid(),
  order_id uuid not null,
  seller_id uuid not null,
  user_id uuid,
  rating integer not null,
  comment text,
  created_at timestamp without time zone default now(),
  constraint review_stores_pkey primary key (id),
  constraint review_stores_order_id_key unique (order_id),
  constraint review_stores_order_id_fkey foreign key (order_id) references public.orders (id) on delete cascade,
  constraint review_stores_seller_id_fkey foreign key (seller_id) references public.seller_profiles (id) on delete cascade,
  constraint review_stores_user_id_fkey foreign key (user_id) references public.users (id),
  constraint review_stores_rating_check check (rating between 1 and 5)
);
create index if not exists idx_review_stores_seller on public.review_stores (seller_id, created_at desc);

create table if not exists public.review_items (
  id uuid not null default gen_random_uuid(),
  order_id uuid not null,
  seller_id uuid not null,
  user_id uuid,
  food_item_id uuid,
  name_snapshot text not null,
  rating integer not null,
  comment text,
  created_at timestamp without time zone default now(),
  constraint review_items_pkey primary key (id),
  -- NULLs are distinct: several deleted dishes of one order don't collide.
  constraint review_items_order_food_key unique (order_id, food_item_id),
  constraint review_items_order_id_fkey foreign key (order_id) references public.orders (id) on delete cascade,
  constraint review_items_seller_id_fkey foreign key (seller_id) references public.seller_profiles (id) on delete cascade,
  constraint review_items_user_id_fkey foreign key (user_id) references public.users (id),
  constraint review_items_food_item_id_fkey foreign key (food_item_id) references public.food_items (id) on delete set null,
  constraint review_items_rating_check check (rating between 1 and 5)
);
create index if not exists idx_review_items_food_item on public.review_items (food_item_id, created_at desc);

-- Public read as reviews had (20260929174120_rls_policies.sql). No insert policy: reviews had
-- "user write own review", which let a buyer insert any rating straight through PostgREST and
-- skip the API's done / paid / own-dish checks. Only the backend (service role) writes.
alter table public.review_stores enable row level security;
alter table public.review_items enable row level security;

drop policy if exists "public read review_stores" on public.review_stores;
create policy "public read review_stores" on public.review_stores for select using (true);

drop policy if exists "public read review_items" on public.review_items;
create policy "public read review_items" on public.review_items for select using (true);

create or replace function public.recalc_review_store_rating() returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  v_seller_id uuid := case when tg_op = 'DELETE' then old.seller_id else new.seller_id end;
begin
  update public.seller_profiles s
     set rating_avg = sub.avg_rating, rating_count = sub.cnt
    from (select round(avg(rating)::numeric, 1) as avg_rating, count(*) as cnt
            from public.review_stores where seller_id = v_seller_id) sub
   where s.id = v_seller_id;
  return null;
end;
$$;

drop trigger if exists on_review_store_change on public.review_stores;
create trigger on_review_store_change
  after insert or update or delete on public.review_stores
  for each row execute function public.recalc_review_store_rating();

-- Old and new dish both: an UPDATE can move a row off a dish (ON DELETE SET NULL). The dish
-- being deleted then matches no row, so nothing is written to it.
create or replace function public.recalc_review_item_rating() returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  v_food_item_id uuid;
begin
  foreach v_food_item_id in array array_remove(array[
      case when tg_op <> 'INSERT' then old.food_item_id end,
      case when tg_op <> 'DELETE' then new.food_item_id end], null)
  loop
    update public.food_items f
       set rating_avg = sub.avg_rating, rating_count = sub.cnt
      from (select round(avg(rating)::numeric, 1) as avg_rating, count(*) as cnt
              from public.review_items where food_item_id = v_food_item_id) sub
     where f.id = v_food_item_id;
  end loop;
  return null;
end;
$$;

drop trigger if exists on_review_item_change on public.review_items;
create trigger on_review_item_change
  after insert or update or delete on public.review_items
  for each row execute function public.recalc_review_item_rating();

comment on column public.seller_profiles.rating_avg is
  'Denormalised from review_stores. Maintained by the on_review_store_change trigger:
   never write it by hand. NULL until the first review.';
comment on column public.food_items.rating_avg is
  'Denormalised from review_items. Maintained by the on_review_item_change trigger:
   never write it by hand. NULL until the first review.';

-- Move existing reviews. Dish rows take the name the order recorded, else the current name.
do $$
begin
  if to_regclass('public.reviews') is null then
    return;
  end if;

  insert into public.review_stores (id, order_id, seller_id, user_id, rating, comment, created_at)
  select id, order_id, seller_id, user_id, rating, comment, created_at
    from public.reviews where food_item_id is null;

  insert into public.review_items (id, order_id, seller_id, user_id, food_item_id, name_snapshot,
                                   rating, comment, created_at)
  select r.id, r.order_id, r.seller_id, r.user_id, r.food_item_id,
         coalesce((select oi.name_snapshot from public.order_items oi
                    where oi.order_id = r.order_id and oi.food_item_id = r.food_item_id
                    limit 1), f.name),
         r.rating, r.comment, r.created_at
    from public.reviews r
    join public.food_items f on f.id = r.food_item_id;
end $$;

-- Drops its indexes, policies and on_review_change trigger with it.
drop table if exists public.reviews;
drop function if exists public.recalc_review_ratings();

-- Danger Zone purge: counts the two new tables instead of reviews (body otherwise unchanged
-- from 20261020000000_admin_purge_orders.sql).
create or replace function public.admin_purge_orders(
  p_seller_id uuid, p_dry_run boolean, p_actor text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_cutoff     int;
  v_cutoff_day date;
  v_orders     uuid[];
  v_deductions uuid[];
  v_apps       uuid[];
  v_payouts    uuid[];
  v_locked     uuid[];
  v_skipped    int;
  v_result     jsonb;
begin
  select (value #>> '{}')::int into v_cutoff
    from public.admin_settings where key = 'purge_orders_before';
  v_cutoff := coalesce(v_cutoff, 99991231);
  v_cutoff_day := to_date(v_cutoff::text, 'YYYYMMDD');

  -- orders.created_at is a UTC timestamp without time zone.
  select coalesce(array_agg(id) filter (
           where ((created_at at time zone 'UTC') at time zone 'Asia/Ho_Chi_Minh')::date < v_cutoff_day), '{}'),
         count(*) filter (
           where ((created_at at time zone 'UTC') at time zone 'Asia/Ho_Chi_Minh')::date >= v_cutoff_day)
    into v_orders, v_skipped
    from public.orders
   where p_seller_id is null or seller_id = p_seller_id;

  select coalesce(array_agg(id), '{}') into v_deductions
    from public.admin_payout_deductions where order_id = any (v_orders);
  select coalesce(array_agg(id), '{}') into v_apps
    from public.admin_payout_deduction_applications where deduction_id = any (v_deductions);

  -- Lock every payout the scope touches so its status can't move under us.
  perform 1 from public.admin_payouts
   where id in (select payout_id from public.orders where id = any (v_orders)
                union
                select payout_id from public.admin_payout_deduction_applications where id = any (v_apps))
     for update;

  select coalesce(array_agg(distinct p.id), '{}') into v_locked
    from public.admin_payouts p
   where p.status in ('processing', 'completed')
     and (p.id in (select payout_id from public.orders where id = any (v_orders))
          or p.id in (select payout_id from public.admin_payout_deduction_applications where id = any (v_apps)));
  if cardinality(v_locked) > 0 then
    return jsonb_build_object('status', 'error', 'reason', 'payout_locked', 'payout_ids', to_jsonb(v_locked));
  end if;

  -- Unpaid payouts of the scope's sellers that nothing outside the scope still points at:
  -- the ones the scope's orders sit in, and any empty one from before the cutoff.
  select coalesce(array_agg(p.id), '{}') into v_payouts
    from public.admin_payouts p
   where (p_seller_id is null or p.seller_id = p_seller_id)
     and p.status in ('pending', 'failed')
     and (p.period_end < v_cutoff_day
          or p.id in (select payout_id from public.orders where id = any (v_orders)))
     and not exists (select 1 from public.orders o
                      where o.payout_id = p.id and o.id <> all (v_orders))
     and not exists (select 1 from public.admin_payout_deduction_applications a
                      where a.payout_id = p.id and a.id <> all (v_apps));

  v_result := jsonb_build_object(
    'status', 'ok',
    'dry_run', p_dry_run,
    'seller_id', p_seller_id,
    'cutoff', v_cutoff,
    'skipped_after_cutoff', v_skipped,
    'seller_count', (select count(distinct seller_id) from public.orders where id = any (v_orders)),
    'orders_by_status', (select coalesce(jsonb_object_agg(status, n), '{}')
                           from (select status, count(*) as n from public.orders
                                  where id = any (v_orders) group by status) s),
    'total_subtotal', (select coalesce(sum(subtotal), 0) from public.orders where id = any (v_orders)),
    'total_payout_amount', (select coalesce(sum(payout_amount), 0) from public.orders where id = any (v_orders)),
    'payout_ids', to_jsonb(v_payouts),
    'counts', jsonb_build_object(
      'orders', cardinality(v_orders),
      'order_items', (select count(*) from public.order_items where order_id = any (v_orders)),
      'payments', (select count(*) from public.payments where order_id = any (v_orders)),
      'deliveries', (select count(*) from public.deliveries where order_id = any (v_orders)),
      'review_stores', (select count(*) from public.review_stores where order_id = any (v_orders)),
      'review_items', (select count(*) from public.review_items where order_id = any (v_orders)),
      'refunds', (select count(*) from public.refunds where order_id = any (v_orders)),
      'history_order_status', (select count(*) from public.history_order_status where order_id = any (v_orders)),
      'history_delivery', (select count(*) from public.history_delivery
                            where order_id = any (v_orders)
                               or delivery_id in (select id from public.deliveries where order_id = any (v_orders))),
      'admin_payout_deductions', cardinality(v_deductions),
      'admin_payout_deduction_applications', cardinality(v_apps),
      'admin_payouts', cardinality(v_payouts)
    )
  );

  if p_dry_run then
    return v_result;
  end if;

  -- FK order: applications → deductions; refunds before orders (no cascade);
  -- orders cascade to order_items, payments, deliveries, review_stores, review_items; payouts last.
  delete from public.admin_payout_deduction_applications where id = any (v_apps);
  delete from public.admin_payout_deductions where id = any (v_deductions);
  delete from public.refunds where order_id = any (v_orders);
  delete from public.history_order_status where order_id = any (v_orders);
  -- order_id is nullable there: match by the scope's deliveries too (before they cascade away).
  delete from public.history_delivery
   where order_id = any (v_orders)
      or delivery_id in (select id from public.deliveries where order_id = any (v_orders));
  delete from public.orders where id = any (v_orders);
  delete from public.admin_payouts where id = any (v_payouts);

  insert into public.history_admin_actions (action, actor, params, result)
  values ('purge_orders', p_actor,
          jsonb_build_object('seller_id', p_seller_id, 'cutoff', v_cutoff),
          v_result);

  return v_result;
end;
$$;

-- Supabase grants anon/authenticated on new public functions: admin backend only.
revoke execute on function public.admin_purge_orders(uuid, boolean, text)
  from public, anon, authenticated;
grant execute on function public.admin_purge_orders(uuid, boolean, text) to service_role;
