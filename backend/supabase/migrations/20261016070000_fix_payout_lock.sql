-- ============================================================
-- Fix admin_generate_payout_for_seller: its step 2 ran FOR UPDATE on an aggregate,
-- which Postgres rejects ("FOR UPDATE is not allowed with aggregate functions"), so
-- the function failed for every seller: on PROD as well (it was copied unchanged
-- from PROD into 20261016050000; PROD has 0 orders ever past payout_status
-- 'pending'). Found by the T5 DEV check (admin repo
-- backend/tests/payout_deductions_dev_check.sql). Same function as 20261016050000
-- except step 2, which now locks with PERFORM ... FOR UPDATE and then aggregates.
-- ============================================================

create or replace function public.admin_generate_payout_for_seller(
  p_seller_id uuid, p_period_start date, p_period_end date,
  p_threshold numeric, p_rate_goods numeric, p_rate_services numeric
) returns jsonb
language plpgsql
as $$
declare
  v_order_count        int;
  v_total_subtotal     numeric := 0;
  v_total_commission   numeric := 0;
  v_total_vat          numeric := 0;
  v_gross_payout       numeric := 0;
  v_ytd_after          numeric := 0;
  v_ytd_before         numeric;
  v_taxable_subtotal   numeric;
  v_tax_category       text;
  v_withholding_rate   numeric := 0;
  v_withholding_amount numeric;
  v_net_payout         numeric;
  v_payout             public.admin_payouts%rowtype;
  v_period_start_ts    timestamp := p_period_start::timestamp;
  v_period_end_ts      timestamp := (p_period_end + 1)::timestamp; -- exclusive upper bound
  v_year_start_ts      timestamp := date_trunc('year', p_period_start)::timestamp;
  -- T5
  v_setting            jsonb;
  v_max_percent        int;
  v_remaining          numeric;
  v_take               numeric;
  v_total_deductions   numeric := 0;
  v_deduction          record;
begin
  -- 1. Fast-path: another batch already created this payout.
  if exists (
    select 1 from public.admin_payouts
    where seller_id = p_seller_id
      and period_start = p_period_start
      and period_end = p_period_end
  ) then
    return jsonb_build_object('status', 'skipped', 'reason', 'payout_exists');
  end if;

  -- 2. Lock, then aggregate, the eligible orders. Postgres rejects FOR UPDATE on an
  --    aggregate ("FOR UPDATE is not allowed with aggregate functions": the old
  --    single statement failed on every call), so the lock is its own statement.
  --    A concurrent batch blocks on the lock until the first commits; the SELECT
  --    after it then sees those rows in 'processing' and aggregates 0.
  perform 1
  from public.orders
  where seller_id = p_seller_id
    and payment_status = 'paid'
    and status = 'done'
    and payout_status = 'pending'
    and payout_hold = false  -- T5: held orders stay out (D5)
    and created_at >= v_period_start_ts
    and created_at <  v_period_end_ts
  for update;

  select
    count(*),
    coalesce(sum(subtotal), 0),
    coalesce(sum(commission_amount), 0),
    coalesce(sum(vat_amount), 0),
    coalesce(sum(payout_amount), 0)
  into v_order_count, v_total_subtotal, v_total_commission, v_total_vat, v_gross_payout
  from public.orders
  where seller_id = p_seller_id
    and payment_status = 'paid'
    and status = 'done'
    and payout_status = 'pending'
    and payout_hold = false
    and created_at >= v_period_start_ts
    and created_at <  v_period_end_ts;

  -- T5: open deductions alone never create a payout (D4); they wait.
  if v_order_count = 0 then
    return jsonb_build_object('status', 'skipped', 'reason', 'no_eligible_orders');
  end if;

  -- 3. Tax category (defaults to 'services' if missing).
  select coalesce(tax_category, 'services')
    into v_tax_category
  from public.seller_profiles
  where id = p_seller_id;
  v_tax_category := coalesce(v_tax_category, 'services');

  -- 4. YTD subtotal capped at period_end so generating an earlier period
  --    after a later one does not over-tax the earlier batch.
  select coalesce(sum(subtotal), 0)
    into v_ytd_after
  from public.orders
  where seller_id = p_seller_id
    and payment_status = 'paid'
    and status = 'done'
    and created_at >= v_year_start_ts
    and created_at <  v_period_end_ts;

  v_ytd_before := v_ytd_after - v_total_subtotal;
  v_taxable_subtotal := greatest(0::numeric, v_ytd_after - greatest(p_threshold, v_ytd_before));

  if v_taxable_subtotal > 0 then
    v_withholding_rate := case when v_tax_category = 'goods'
                               then p_rate_goods else p_rate_services end;
  end if;

  v_withholding_amount := round(v_taxable_subtotal * v_withholding_rate, 2);
  if v_withholding_amount > v_gross_payout then
    v_withholding_amount := v_gross_payout;
  end if;
  v_net_payout := round(v_gross_payout - v_withholding_amount, 2);

  -- 5. Insert payout row. Unique index on (seller_id, period_start,
  --    period_end) provides the final guard — a concurrent insert will
  --    raise unique_violation, which we surface as a skip.
  insert into public.admin_payouts (
    seller_id, period_start, period_end, order_count,
    total_subtotal, total_commission, total_vat, gross_payout,
    withholding_rate, withholding_amount, net_payout, status
  ) values (
    p_seller_id, p_period_start, p_period_end, v_order_count,
    round(v_total_subtotal, 2), round(v_total_commission, 2),
    round(v_total_vat, 2), round(v_gross_payout, 2),
    v_withholding_rate, v_withholding_amount, v_net_payout, 'pending'
  )
  returning * into v_payout;

  -- 6. Stamp the rows we already locked. Same WHERE as step 2 — only
  --    rows still 'pending' are touched. Because they are locked by us,
  --    no concurrent writer can change them between step 2 and here.
  update public.orders
     set payout_status = 'processing',
         payout_id     = v_payout.id
   where seller_id = p_seller_id
     and payment_status = 'paid'
     and status = 'done'
     and payout_status = 'pending'
     and payout_hold = false  -- T5
     and created_at >= v_period_start_ts
     and created_at <  v_period_end_ts;

  -- 7. T5: take open deductions, oldest first, up to payout_deduction_max_percent
  --    of the net (after withholding, which stays computed on the orders: D6).
  --    Missing / not an integer > 0 → 100; above 100 → 100.
  select value into v_setting from public.admin_settings where key = 'payout_deduction_max_percent';
  if jsonb_typeof(v_setting) = 'number' and (v_setting #>> '{}') ~ '^[0-9]+$' then
    v_max_percent := (v_setting #>> '{}')::int;
  end if;
  if v_max_percent is null or v_max_percent < 1 then
    if v_setting is not null then
      raise warning 'admin_settings payout_deduction_max_percent=% invalid, using 100', v_setting;
    end if;
    v_max_percent := 100;
  elsif v_max_percent > 100 then
    raise warning 'admin_settings payout_deduction_max_percent=% above 100, using 100', v_max_percent;
    v_max_percent := 100;
  end if;

  v_remaining := round(v_net_payout * v_max_percent / 100);
  for v_deduction in
    select id, amount, applied_amount
    from public.admin_payout_deductions
    where seller_id = p_seller_id
      and applied_amount < amount
    order by created_at, id
    for update
  loop
    exit when v_remaining <= 0;
    v_take := least(v_deduction.amount - v_deduction.applied_amount, v_remaining);
    update public.admin_payout_deductions
       set applied_amount = applied_amount + v_take
     where id = v_deduction.id;
    insert into public.admin_payout_deduction_applications (deduction_id, payout_id, amount)
    values (v_deduction.id, v_payout.id, v_take);
    v_remaining := v_remaining - v_take;
    v_total_deductions := v_total_deductions + v_take;
  end loop;

  if v_total_deductions > 0 then
    update public.admin_payouts
       set total_deductions = v_total_deductions,
           net_payout       = v_net_payout - v_total_deductions
     where id = v_payout.id
     returning * into v_payout;
  end if;

  return jsonb_build_object(
    'status', 'created',
    'payout', to_jsonb(v_payout)
  );

exception
  when unique_violation then
    return jsonb_build_object('status', 'skipped', 'reason', 'concurrent_create');
end;
$$;

-- create or replace keeps the ACL set in 20261016050000; restated so this file
-- stands on its own.
revoke execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric) to service_role;
