-- ============================================================
-- Payout hold + seller-fault refund deductions (admin repo TODO T5).
-- Spec: docs/dev/refund-ops/README.md §1, §1.1, §3.1, §3.2 (D1–D5).
--   * orders.payout_hold: admin keeps a disputed order out of every payout (D5).
--   * admin_payout_deductions: amount a seller owes back (D1), taken from their next
--     payouts oldest first, capped per payout (D3), left open when there is
--     nothing to take from (D4). admin_payout_deduction_applications records how much
--     each payout took, so a payout marked 'failed' gives exactly its share back.
--   * 2 business parameters in admin_settings (no hardcoded numbers).
--   * The 3 payout functions below are the PROD definitions (identical to the admin
--     repo's backend/src/sql/payout_rpc.sql, checked against reference/schema_prod.sql)
--     plus the T5 changes, marked "T5". DEV has none of the admin_* functions; this
--     creates them there.
--   * Execute on the 4 admin_* functions revoked from public/anon/authenticated:
--     only the admin backend (service_role) calls them.
-- Expand-only for the marketplace backend (it reads none of this).
-- ============================================================

-- 1. Payout hold on orders (D5)
alter table public.orders add column if not exists payout_hold boolean not null default false;
alter table public.orders add column if not exists payout_hold_note text;

-- 2. Deductions (D1–D4)
create table if not exists public.admin_payout_deductions (
  id uuid not null default gen_random_uuid(),
  seller_id uuid not null,                     -- seller_profiles.id
  order_id uuid not null,
  refund_id uuid,                              -- refund that caused it, if any
  amount numeric not null,                     -- VND owed back
  reason text not null,
  created_by text,                             -- admin email
  created_at timestamp with time zone not null default now(),
  applied_amount numeric not null default 0,   -- running total taken from payouts
  constraint admin_payout_deductions_pkey primary key (id),
  constraint admin_payout_deductions_amount_check
    check (amount > 0 and applied_amount >= 0 and applied_amount <= amount)
);
create index if not exists admin_payout_deductions_seller_open_idx
  on public.admin_payout_deductions (seller_id) where applied_amount < amount;
alter table public.admin_payout_deductions enable row level security;

create table if not exists public.admin_payout_deduction_applications (
  id uuid not null default gen_random_uuid(),
  deduction_id uuid not null references public.admin_payout_deductions (id),
  payout_id uuid not null references public.admin_payouts (id),
  amount numeric not null check (amount > 0),
  created_at timestamp with time zone not null default now(),
  constraint admin_payout_deduction_applications_pkey primary key (id),
  constraint admin_payout_deduction_applications_once unique (deduction_id, payout_id)
);
create index if not exists admin_payout_deduction_applications_payout_idx
  on public.admin_payout_deduction_applications (payout_id);
alter table public.admin_payout_deduction_applications enable row level security;

alter table public.admin_payouts add column if not exists total_deductions numeric not null default 0;

-- 3. Business parameters (§1.1), editable on the admin Settings page
insert into public.admin_settings (key, value, description)
values
  ('payout_deduction_percent', '100'::jsonb,
   'Percent (integer 1-100) of the seller''s share of an order (orders.payout_amount) deducted from their next payouts when an admin cancels an order already in a payout and ticks "Charge to seller".'),
  ('payout_deduction_max_percent', '100'::jsonb,
   'Percent (integer 1-100) of a payout''s net amount that open deductions may take; the rest carries over to later payouts.')
on conflict (key) do nothing;

-- 4. Per-seller payout (PROD body + T5)
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

  -- 2. Lock & aggregate eligible orders. FOR UPDATE serializes concurrent
  --    batches: a second caller blocks here until the first commits, then
  --    sees the rows already in 'processing' and aggregates 0.
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
    and payout_hold = false  -- T5: held orders stay out (D5)
    and created_at >= v_period_start_ts
    and created_at <  v_period_end_ts
  for update;

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

-- 5. Batch over sellers (PROD body + T5: skip sellers whose only eligible orders are held)
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
begin
  for v_seller_id in
    select distinct seller_id
    from public.orders
    where payment_status = 'paid'
      and status = 'done'
      and payout_status = 'pending'
      and payout_hold = false  -- T5
      and seller_id is not null
      and created_at >= p_period_start::timestamp
      and created_at <  (p_period_end + 1)::timestamp
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

-- 6. Payout status (PROD body + T5: a failed payout gives its deductions back)
create or replace function public.admin_update_payout_status(
  p_payout_id uuid, p_new_status text, p_note text default null
) returns jsonb
language plpgsql
as $$
declare
  v_current_status text;
  v_paid_at        timestamptz;
  v_updated        public.admin_payouts%rowtype;
begin
  -- Lock the payout row so concurrent status updates serialize.
  select status into v_current_status
  from public.admin_payouts
  where id = p_payout_id
  for update;

  if not found then
    return jsonb_build_object('status', 'error', 'reason', 'not_found');
  end if;

  -- Forward-only state machine.
  if not (
    (v_current_status = 'pending'    and p_new_status in ('processing', 'failed')) or
    (v_current_status = 'processing' and p_new_status in ('completed', 'failed'))
  ) then
    return jsonb_build_object(
      'status', 'error',
      'reason', 'invalid_transition',
      'detail', format('cannot transition from %s to %s', v_current_status, p_new_status)
    );
  end if;

  if p_new_status = 'completed' then
    v_paid_at := now();
  end if;

  update public.admin_payouts
     set status  = p_new_status,
         note    = coalesce(p_note, note),
         paid_at = coalesce(v_paid_at, paid_at)
   where id = p_payout_id
   returning * into v_updated;

  -- Side effect on orders, atomic with the payout update.
  if p_new_status = 'completed' then
    update public.orders
       set payout_status = 'paid_out'
     where payout_id = p_payout_id;
  elsif p_new_status = 'failed' then
    update public.orders
       set payout_status = 'pending',
           payout_id     = null
     where payout_id = p_payout_id;

    -- T5: nothing was paid, so nothing was taken: reopen exactly this payout's
    -- share of each deduction (one application row per deduction per payout).
    update public.admin_payout_deductions d
       set applied_amount = d.applied_amount - a.amount
      from public.admin_payout_deduction_applications a
     where a.payout_id = p_payout_id
       and a.deduction_id = d.id;
    delete from public.admin_payout_deduction_applications
     where payout_id = p_payout_id;
  end if;

  return jsonb_build_object('status', 'ok', 'payout', to_jsonb(v_updated));
end;
$$;

-- 7. Only the admin backend (service_role) may run the admin_* functions. After the
--    create-or-replace above: Supabase grants anon/authenticated on new public functions.
revoke execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
revoke execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
revoke execute on function public.admin_update_payout_status(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric) to service_role;
grant execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric) to service_role;
grant execute on function public.admin_update_payout_status(uuid, text, text) to service_role;

-- admin_mark_refund_processed exists only on PROD (not recreated here).
do $$
begin
  if to_regprocedure('public.admin_mark_refund_processed(uuid, text)') is not null then
    revoke execute on function public.admin_mark_refund_processed(uuid, text) from public, anon, authenticated;
    grant execute on function public.admin_mark_refund_processed(uuid, text) to service_role;
  end if;
end;
$$;
