-- ============================================================
-- Weekly seller payouts made automatically (docs/dev/payout-auto; Jack 2026-10-26).
-- 1. Settings: payout_period_weeks (1), payout_weekday (2 = Tuesday), payout_generate_hour (8) replace
--    payout_delay_days / payout_cycle_days / payout_cycle_start_date (deleted at the end of this file).
-- 2. Complaint safety instead of a fixed delay (Q2): an order goes into a payout only once its complaint
--    window (complaint_window_hours after it became done) is over when the payout is made. One helper,
--    admin_payout_done_before(), gives the cut-off; both generate functions use it, and the
--    period_not_ready refusal is gone.
-- 3. Cancel a waiting payout (D2): status 'cancelled' (row kept for the books), orders and deductions back
--    as before; the duplicate guard ignores cancelled rows so the same period can be made again.
-- 4. admin_payout_runs (D3): one row per automatic run (period_end), claimed with insert … on conflict do
--    nothing, so a period is made and emailed once even with several backend processes or a restart.
-- Money is unchanged: same sums, same deductions; only which orders and when.
-- Replaces 20261021050000 (admin_generate_payouts) / 20261021080000 (admin_generate_payout_for_seller).
-- ============================================================

-- 1. Settings (the admin Settings page shows them under Payouts)
insert into public.admin_settings (key, value, description) values
  ('payout_period_weeks', '1'::jsonb,
   'Weeks (integer 1-4) in one seller payout period. A period runs Monday 00:00 to Sunday 23:59 (Vietnam time); with more than 1 week the periods follow each other from Monday 2026-10-26.'),
  ('payout_weekday', '2'::jsonb,
   'Payout day after a period ends: 1 = Monday ... 7 = Sunday (2 = Tuesday). On that day the admin backend makes the payouts of the period that just ended.'),
  ('payout_generate_hour', '8'::jsonb,
   'Hour (integer 0-23, Vietnam time) on the payout day from which the admin backend makes the payouts automatically (when PAYOUT_AUTO_GENERATE=1).')
on conflict (key) do nothing;

-- 2. Cut-off: orders done before this (exclusive) can go into a payout for a period ending p_period_end.
create or replace function public.admin_payout_done_before(p_period_end date)
returns timestamptz
language plpgsql
stable
as $$
declare
  v_setting jsonb;
  v_hours   int;
begin
  -- complaint_window_hours: integer > 0; missing / invalid -> 24 (same default as the complaints API).
  select value into v_setting from public.admin_settings where key = 'complaint_window_hours';
  if jsonb_typeof(v_setting) = 'number' and (v_setting #>> '{}') ~ '^[0-9]+$' then
    v_hours := (v_setting #>> '{}')::int;
  end if;
  if v_hours is null or v_hours < 1 then
    if v_setting is not null then
      raise warning 'admin_settings complaint_window_hours=% invalid, using 24', v_setting;
    end if;
    v_hours := 24;
  end if;
  return least((p_period_end + 1)::timestamp at time zone 'Asia/Ho_Chi_Minh', now() - make_interval(hours => v_hours));
end;
$$;

revoke execute on function public.admin_payout_done_before(date) from public, anon, authenticated;
grant execute on function public.admin_payout_done_before(date) to service_role;

-- 3. Payout status 'cancelled' + who / when; duplicate guard without cancelled rows
alter table public.admin_payouts add column if not exists cancelled_at timestamptz;
alter table public.admin_payouts add column if not exists cancelled_by text;
alter table public.admin_payouts drop constraint if exists admin_payouts_status_check;
alter table public.admin_payouts add constraint admin_payouts_status_check
  check (status = any (array['pending', 'processing', 'completed', 'failed', 'cancelled']));
create unique index if not exists admin_payouts_seller_period_uidx
  on public.admin_payouts (seller_id, period_start, period_end) where status <> 'cancelled';

-- 4. Per seller: body = 20261021080000 except the cut-off (v_done_to) and the fast-path skipping cancelled rows.
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
  -- exclusive: end of period_end (VN), or earlier while the complaint window is still open (payout-auto Q2)
  v_done_to            timestamptz := public.admin_payout_done_before(p_period_end);
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
      and status <> 'cancelled'  -- a cancelled payout can be made again (payout-auto D2)
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

  -- 5. Insert payout row. Unique index on (seller_id, period_start, period_end), cancelled rows aside, is the final
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

-- 5. Batch: no period_not_ready any more; sellers with an eligible order before the cut-off.
create or replace function public.admin_generate_payouts(
  p_period_start date, p_period_end date
) returns jsonb
language plpgsql
as $$
declare
  v_seller_id  uuid;
  v_result     jsonb;
  v_created    jsonb := '[]'::jsonb;
  v_skipped    int   := 0;
  v_errors     jsonb := '[]'::jsonb;
  v_done_from  timestamptz := p_period_start::timestamp at time zone 'Asia/Ho_Chi_Minh';
  v_done_to    timestamptz := public.admin_payout_done_before(p_period_end); -- exclusive
begin
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
      v_result := public.admin_generate_payout_for_seller(v_seller_id, p_period_start, p_period_end);
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

revoke execute on function public.admin_generate_payouts(date, date) from public, anon, authenticated;
grant execute on function public.admin_generate_payouts(date, date) to service_role;

-- 6. Cancel a payout still waiting (pending): orders and this payout's deductions back exactly as before it
--    was made (same as the failed branch of admin_update_payout_status); the row stays as 'cancelled'.
create or replace function public.admin_cancel_payout(p_payout_id uuid, p_cancelled_by text default null)
returns jsonb
language plpgsql
as $$
declare
  v_status  text;
  v_orders  int;
  v_payout  public.admin_payouts%rowtype;
begin
  select status into v_status from public.admin_payouts where id = p_payout_id for update;
  if not found then
    return jsonb_build_object('status', 'error', 'reason', 'not_found');
  end if;
  if v_status <> 'pending' then
    return jsonb_build_object('status', 'error', 'reason', 'not_pending', 'current', v_status);
  end if;

  update public.orders
     set payout_status = 'pending',
         payout_id     = null
   where payout_id = p_payout_id;
  get diagnostics v_orders = row_count;

  update public.admin_payout_deductions d
     set applied_amount = d.applied_amount - a.amount
    from public.admin_payout_deduction_applications a
   where a.payout_id = p_payout_id
     and a.deduction_id = d.id;
  delete from public.admin_payout_deduction_applications where payout_id = p_payout_id;

  update public.admin_payouts
     set status = 'cancelled', cancelled_at = now(), cancelled_by = p_cancelled_by
   where id = p_payout_id
  returning * into v_payout;

  return jsonb_build_object('status', 'ok', 'payout', to_jsonb(v_payout), 'orders_returned', v_orders);
end;
$$;

revoke execute on function public.admin_cancel_payout(uuid, text) from public, anon, authenticated;
grant execute on function public.admin_cancel_payout(uuid, text) to service_role;

-- 7. Automatic runs: one row per period (period_end), so a period is made and emailed once.
create table if not exists public.admin_payout_runs (
  period_end    date        primary key,
  period_start  date        not null,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  result        jsonb,       -- {created, skipped, errors} of admin_generate_payouts, or {"existing": n}
  email_sent_at timestamptz
);
alter table public.admin_payout_runs enable row level security;   -- service role only (admin backend)
comment on table public.admin_payout_runs is
  'One row per automatic payout run (admin backend, PAYOUT_AUTO_GENERATE): claimed with insert on conflict do nothing, so each period is made and emailed once.';

-- 8. The old payout timing settings are not read any more (sariko-app earnings, admin next-period / generate).
delete from public.admin_settings where key in ('payout_delay_days', 'payout_cycle_days', 'payout_cycle_start_date');
