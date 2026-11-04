-- ============================================================
-- T105: monthly plan fee taken from the seller's payouts (docs/dev/tax-withholding/README.md, section F).
-- * One fee per seller and calendar month (Vietnam time) = admin_tier_config.monthly_fee_vnd of the
--   seller's plan when it is charged (0 = nothing, e.g. community). The first month is charged in full (F2).
-- * Charged from the seller's start month = max(admin_settings fee_start_date, the day the store was
--   created): seller_profiles has no activation date, created_at is the T4 mark already used for the
--   founding months (F1). fee_start_date 99991231 = no fee yet.
-- * founding: the first founding_free_months months from that start are free.
-- * When a payout is created, every month from the start up to the current one that has no fee yet
--   becomes an admin_payout_deductions row (fee_month, no order): months without a payout are charged
--   at the next one (F3), and the existing deduction rules apply (max percent per payout, the rest
--   carries over, a failed payout gives its share back). Unique (seller_id, fee_month): never twice.
-- Replaces the 20261021050000 body of admin_generate_payout_for_seller (one call added, step 7a).
-- ============================================================

insert into public.admin_settings (key, value, description) values
  ('fee_start_date', '99991231'::jsonb,
   'Day (YYYYMMDD, Vietnam time) from which sellers pay the monthly plan fee, taken from their payouts. A seller starts at the later of this day and the day their store was created. 99991231 = not charging yet.')
on conflict (key) do nothing;

-- A deduction is either for an order (refund) or a monthly fee.
alter table public.admin_payout_deductions alter column order_id drop not null;
alter table public.admin_payout_deductions add column if not exists fee_month date;  -- first day of the month
alter table public.admin_payout_deductions drop constraint if exists admin_payout_deductions_source_check;
alter table public.admin_payout_deductions add constraint admin_payout_deductions_source_check
  check (order_id is not null or fee_month is not null);
create unique index if not exists admin_payout_deductions_fee_month_uidx
  on public.admin_payout_deductions (seller_id, fee_month) where fee_month is not null;

-- Creates the missing monthly fee rows of one seller; returns how many.
create or replace function public.admin_charge_monthly_fees(p_seller_id uuid)
returns int
language plpgsql
as $$
declare
  v_setting    jsonb;
  v_start      date;
  v_tier       text;
  v_fee        numeric;
  v_created_on date;
  v_free       int := 0;
  v_month      date;
  v_index      int := 0;
  v_rows       int;
  v_created    int := 0;
  v_this_month date := date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh')::date;
begin
  -- fee_start_date: YYYYMMDD; missing / not a date -> no fee (warning when a value is set)
  select value into v_setting from public.admin_settings where key = 'fee_start_date';
  begin
    if jsonb_typeof(v_setting) = 'number' and (v_setting #>> '{}') ~ '^[0-9]{8}$' then
      v_start := to_date(v_setting #>> '{}', 'YYYYMMDD');
    end if;
  exception when others then
    v_start := null;
  end;
  if v_start is null then
    if v_setting is not null then
      raise warning 'admin_settings fee_start_date=% invalid (YYYYMMDD), no monthly fee charged', v_setting;
    end if;
    return 0;
  end if;

  select sp.tier, t.monthly_fee_vnd, (sp.created_at at time zone 'UTC' at time zone 'Asia/Ho_Chi_Minh')::date
    into v_tier, v_fee, v_created_on
  from public.seller_profiles sp
  join public.admin_tier_config t on t.tier = sp.tier
  where sp.id = p_seller_id;
  if coalesce(v_fee, 0) <= 0 then
    return 0;
  end if;
  v_start := date_trunc('month', greatest(v_start, coalesce(v_created_on, v_start)))::date;

  if v_tier = 'founding' then
    select value into v_setting from public.admin_settings where key = 'founding_free_months';
    if jsonb_typeof(v_setting) = 'number' and (v_setting #>> '{}') ~ '^[0-9]+$' then
      v_free := (v_setting #>> '{}')::int;
    else
      raise warning 'admin_settings founding_free_months=% invalid, using 4', v_setting;
      v_free := 4;
    end if;
  end if;

  for v_month in select generate_series(v_start, v_this_month, interval '1 month')::date loop
    if v_index >= v_free then
      insert into public.admin_payout_deductions (seller_id, amount, reason, created_by, fee_month)
      values (p_seller_id, v_fee, 'monthly_fee', 'system', v_month)
      on conflict (seller_id, fee_month) where fee_month is not null do nothing;
      get diagnostics v_rows = row_count;
      v_created := v_created + v_rows;
    end if;
    v_index := v_index + 1;
  end loop;
  return v_created;
end;
$$;

revoke execute on function public.admin_charge_monthly_fees(uuid) from public, anon, authenticated;
grant execute on function public.admin_charge_monthly_fees(uuid) to service_role;

create or replace function public.admin_generate_payout_for_seller(
  p_seller_id uuid, p_period_start date, p_period_end date
) returns jsonb
language plpgsql
as $$
declare
  v_order_count        int;
  v_total_subtotal     numeric := 0;
  v_total_commission   numeric := 0;
  v_total_vat          numeric := 0;
  v_gross_payout       numeric := 0;
  v_withholding_total  numeric := 0;
  v_withholding_amount numeric;
  v_net_payout         numeric;
  v_payout             public.admin_payouts%rowtype;
  v_order_id           uuid;
  -- Period = the days (Vietnam time) on which the orders became done (status_changed_at).
  v_done_from          timestamptz := p_period_start::timestamp at time zone 'Asia/Ho_Chi_Minh';
  v_done_to            timestamptz := (p_period_end + 1)::timestamp at time zone 'Asia/Ho_Chi_Minh'; -- exclusive
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
  --    aggregate, so the lock is its own statement. A concurrent batch blocks on the lock
  --    until the first commits; the SELECT after it then sees those rows in 'processing'.
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

  -- 3. Orders whose withholding was not computed at payment (IPN error, older orders): now.
  for v_order_id in
    select id
    from public.orders
    where seller_id = p_seller_id
      and payment_status = 'paid'
      and status = 'done'
      and payout_status = 'pending'
      and payout_hold = false
      and status_changed_at >= v_done_from
      and status_changed_at <  v_done_to
      and wh_computed_at is null
    order by paid_at nulls last, created_at
  loop
    perform public.compute_order_withholding(v_order_id);
  end loop;

  select
    count(*),
    coalesce(sum(subtotal), 0),
    coalesce(sum(commission_amount), 0),
    coalesce(sum(vat_amount), 0),
    coalesce(sum(payout_amount), 0),
    coalesce(sum(wh_vat_amount + wh_pit_amount), 0)
  into v_order_count, v_total_subtotal, v_total_commission, v_total_vat, v_gross_payout, v_withholding_total
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

  -- 4. Withholding = the orders' snapshots. Never more than gross: the rest is reported, not dropped.
  v_withholding_amount := least(v_withholding_total, v_gross_payout);
  if v_withholding_total > v_withholding_amount then
    raise warning 'admin_generate_payout_for_seller: seller % period %..% withholding % above gross %, short by %',
      p_seller_id, p_period_start, p_period_end, v_withholding_total, v_gross_payout,
      v_withholding_total - v_withholding_amount;
  end if;
  v_net_payout := round(v_gross_payout - v_withholding_amount, 2);

  -- 5. Insert payout row. Unique index on (seller_id, period_start, period_end) is the final
  --    guard: a concurrent insert raises unique_violation, surfaced as a skip.
  insert into public.admin_payouts (
    seller_id, period_start, period_end, order_count,
    total_subtotal, total_commission, total_vat, gross_payout,
    withholding_rate, withholding_amount, net_payout, status
  ) values (
    p_seller_id, p_period_start, p_period_end, v_order_count,
    round(v_total_subtotal, 2), round(v_total_commission, 2),
    round(v_total_vat, 2), round(v_gross_payout, 2),
    null, v_withholding_amount, v_net_payout, 'pending'
  )
  returning * into v_payout;

  -- 6. Stamp the rows we already locked. Same WHERE as step 2.
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

  -- 7a. T105: monthly fees owed up to this month become deductions (once per seller and month),
  --     taken by step 7 like any other deduction, so the same cap and carry-over apply.
  perform public.admin_charge_monthly_fees(p_seller_id);

  -- 7. T5: take open deductions, oldest first, up to payout_deduction_max_percent of the net
  --    (after withholding). Missing / not an integer > 0 → 100; above 100 → 100.
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
    'payout', to_jsonb(v_payout),
    'withholding_shortfall', v_withholding_total - v_withholding_amount
  );

exception
  when unique_violation then
    return jsonb_build_object('status', 'skipped', 'reason', 'concurrent_create');
end;
$$;

revoke execute on function public.admin_generate_payout_for_seller(uuid, date, date)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payout_for_seller(uuid, date, date) to service_role;
