-- ============================================================
-- Seller payouts T+3 (docs/dev/payout-cycle/README.md; Jack 2026-10-20: T = when the order
-- becomes done, pay T+3 day by day).
-- 1. admin_settings.payout_delay_days (default 3, valid 0..30; invalid -> 3 + warning).
-- 2. A payout period now means "orders completed on these days (Vietnam time)":
--    status_changed_at instead of created_at, in admin_generate_payouts and
--    admin_generate_payout_for_seller (lock, aggregate, stamp). Filtering created_at by a
--    "done >= 3 days" rule instead would leave orders stuck in 'pending' (spec §1).
-- 3. admin_generate_payouts refuses a period ending after today - payout_delay_days
--    (Vietnam date): {"status":"error","reason":"period_not_ready","earliest_end": date}.
--    (earliest_end = the latest period_end allowed today.)
-- Unchanged: YTD sum for withholding (created_at), deductions, payout_hold, duplicate guard.
-- 20261016050000 / 20261016070000 are on develop: replaced here with create or replace.
-- ============================================================

-- 1. Setting (admin Settings page shows it under Payouts)
insert into public.admin_settings (key, value, description) values
  ('payout_delay_days', '3'::jsonb,
   'Days (integer 0-30) after an order becomes done (status_changed_at, Vietnam date) before it can go into a payout. 3 = T+3. Invalid values fall back to 3.')
on conflict (key) do nothing;

-- 2. Per seller: period by completion day (Vietnam time). Body = 20261016070000 except the
--    three period filters and the variables they use.
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
  -- Period = the days (Vietnam time) on which the orders became done (status_changed_at,
  -- timestamptz). The YTD sum for withholding (step 4) stays on created_at: spec §2.1.
  v_done_from          timestamptz := p_period_start::timestamp at time zone 'Asia/Ho_Chi_Minh';
  v_done_to            timestamptz := (p_period_end + 1)::timestamp at time zone 'Asia/Ho_Chi_Minh'; -- exclusive
  v_period_end_ts      timestamp := (p_period_end + 1)::timestamp; -- exclusive upper bound (YTD only)
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
    and status_changed_at >= v_done_from
    and status_changed_at <  v_done_to
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
    and status_changed_at >= v_done_from
    and status_changed_at <  v_done_to;

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
     and status_changed_at >= v_done_from
     and status_changed_at <  v_done_to;

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

-- ACL as in 20261016050000, restated so this file stands on its own.
revoke execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric) to service_role;

-- 3. Batch: refuse periods that are not T+payout_delay_days old yet; sellers by completion day.
create or replace function public.admin_generate_payouts(
  p_period_start date, p_period_end date,
  p_threshold numeric, p_rate_goods numeric, p_rate_services numeric
) returns jsonb
language plpgsql
as $$
declare
  v_seller_id  uuid;
  v_result     jsonb;
  v_created    jsonb := '[]'::jsonb;
  v_skipped    int   := 0;
  v_errors     jsonb := '[]'::jsonb;
  v_setting    jsonb;
  v_delay      int;
  v_latest_end date;
  v_done_from  timestamptz := p_period_start::timestamp at time zone 'Asia/Ho_Chi_Minh';
  v_done_to    timestamptz := (p_period_end + 1)::timestamp at time zone 'Asia/Ho_Chi_Minh'; -- exclusive
begin
  -- payout_delay_days: integer 0..30; missing / invalid -> 3 (warning when a value is set).
  select value into v_setting from public.admin_settings where key = 'payout_delay_days';
  if jsonb_typeof(v_setting) = 'number' and (v_setting #>> '{}') ~ '^[0-9]+$' then
    v_delay := (v_setting #>> '{}')::int;
  end if;
  if v_delay is null or v_delay > 30 then
    if v_setting is not null then
      raise warning 'admin_settings payout_delay_days=% invalid (integer 0-30), using 3', v_setting;
    end if;
    v_delay := 3;
  end if;

  v_latest_end := (now() at time zone 'Asia/Ho_Chi_Minh')::date - v_delay;
  if p_period_end > v_latest_end then
    return jsonb_build_object('status', 'error', 'reason', 'period_not_ready', 'earliest_end', v_latest_end);
  end if;

  for v_seller_id in
    select distinct seller_id
    from public.orders
    where payment_status = 'paid'
      and status = 'done'
      and payout_status = 'pending'
      and payout_hold = false  -- T5
      and seller_id is not null
      and status_changed_at >= v_done_from
      and status_changed_at <  v_done_to
  loop
    begin
      v_result := public.admin_generate_payout_for_seller(
        v_seller_id, p_period_start, p_period_end,
        p_threshold, p_rate_goods, p_rate_services
      );
      if v_result->>'status' = 'created' then
        v_created := v_created || jsonb_build_array(v_result->'payout');
      else
        v_skipped := v_skipped + 1;
      end if;
    exception when others then
      v_errors := v_errors || jsonb_build_array(
        jsonb_build_object('seller_id', v_seller_id, 'error', sqlerrm)
      );
    end;
  end loop;

  return jsonb_build_object(
    'created', v_created,
    'skipped', v_skipped,
    'errors',  v_errors
  );
end;
$$;

revoke execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric) to service_role;
