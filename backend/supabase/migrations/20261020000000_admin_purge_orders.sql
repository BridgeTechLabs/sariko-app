-- ============================================================
-- Admin Danger Zone: hard-delete test orders (phase 1 of admin test mode).
-- Spec: docs/dev/admin-danger-zone/README.md.
--   * admin_settings purge_orders_before: YYYYMMDD (VN date). Only orders created
--     before that VN date can be purged; 99991231 = no limit (the default until
--     VNPay goes live). Integer, so the admin Settings page can edit it as is.
--   * history_admin_actions: who purged what (one row per real purge).
--   * admin_purge_orders(seller, dry_run, actor): counts (dry run) or deletes, in one
--     transaction, the orders of one seller (NULL = every seller) and everything that
--     hangs off them. Refused when money may have moved: an order or one of its
--     deductions sits in a payout that is processing / completed.
-- Rating columns (seller_profiles / food_items rating_avg, rating_count) need no
-- code here: on_review_change recalculates them for every review the order cascade
-- deletes. history_* triggers fire on insert/update only, so nothing is re-logged.
-- Expand-only: the marketplace backend reads none of this.
-- ============================================================

-- 1. Cutoff (business parameter, editable on the admin Settings page)
insert into public.admin_settings (key, value, description)
values ('purge_orders_before', '99991231'::jsonb,
        'Danger Zone: only orders created before this date (YYYYMMDD, Vietnam time) can be deleted. 99991231 = no limit. Set it to the go-live date when VNPay goes live.')
on conflict (key) do nothing;

-- 2. Admin action log
create table if not exists public.history_admin_actions (
  id bigint generated always as identity,
  action text not null,
  actor text,                                  -- admin email
  params jsonb,
  result jsonb,
  created_at timestamp with time zone not null default now(),
  constraint history_admin_actions_pkey primary key (id)
);
create index if not exists history_admin_actions_created_idx
  on public.history_admin_actions (created_at desc);
-- Backend-only (service role); no policies → anon/authenticated get nothing.
alter table public.history_admin_actions enable row level security;

-- 3. Purge
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
      'reviews', (select count(*) from public.reviews where order_id = any (v_orders)),
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
  -- orders cascade to order_items, payments, deliveries, reviews; payouts last.
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
