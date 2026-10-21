-- ============================================================
-- Seller tax withholding per order (docs/dev/tax-withholding/README.md, T53 + T54 phase 1).
-- Decree 252/2026 Art. 43-46: the platform withholds the seller's VAT + PIT on each order
-- when the payment succeeds. Rates and the threshold live in admin_tax_config (admin Settings).
-- 1. Parameters: 9 rates (3 categories x VAT / PIT resident / PIT non-resident).
-- 2. seller_profiles: tax_category 'goods_services'; tax_resident (null = unknown -> non-resident rate).
-- 3. orders.wh_*: per-order snapshot, written once by compute_order_withholding().
-- 4. compute_order_withholding(order_id): called by the backend after the IPN marks the order paid.
-- 5. Payouts: withholding = sum of the orders' snapshots (orders not computed yet are computed
--    first); the RPCs read admin_tax_config themselves, so they lose the rate / threshold params.
--    The old 5-param admin_generate_payouts stays as a wrapper until the admin app stops passing
--    them (drop in a later migration). Replaces the 20261020030000 bodies.
-- ============================================================

-- 1. Parameters (fractions, e.g. 0.01 = 1%)
insert into public.admin_tax_config (key, rate, description) values
  ('wh_vat_goods',                      0.01,  'Seller VAT withheld per order, goods (Decree 252/2026 Art. 43)'),
  ('wh_pit_goods_resident',             0.005, 'Seller PIT withheld per order, goods, tax resident'),
  ('wh_pit_goods_nonresident',          0.01,  'Seller PIT withheld per order, goods, non-resident or residency unknown'),
  ('wh_vat_services',                   0.05,  'Seller VAT withheld per order, services'),
  ('wh_pit_services_resident',          0.02,  'Seller PIT withheld per order, services, tax resident'),
  ('wh_pit_services_nonresident',       0.05,  'Seller PIT withheld per order, services, non-resident or residency unknown'),
  ('wh_vat_goods_services',             0.03,  'Seller VAT withheld per order, transport / services tied to goods (food service)'),
  ('wh_pit_goods_services_resident',    0.015, 'Seller PIT withheld per order, services tied to goods, tax resident'),
  ('wh_pit_goods_services_nonresident', 0.02,  'Seller PIT withheld per order, services tied to goods, non-resident or residency unknown'),
  ('annual_revenue_threshold',          100000000, 'Annual VND revenue per seller (calendar year, Vietnam time) above which tax is withheld; only the part above it is taxed')
on conflict (key) do nothing;

update public.admin_tax_config
   set description = 'DEPRECATED (replaced by wh_* per order, 20261021050000). Kept until the new payout RPC is proven; not used.'
 where key in ('withholding_rate_goods', 'withholding_rate_services');

-- 2. Seller tax profile
alter table public.seller_profiles drop constraint if exists seller_profiles_tax_category_check;
alter table public.seller_profiles add constraint seller_profiles_tax_category_check
  check (tax_category in ('goods', 'services', 'goods_services'));
alter table public.seller_profiles add column if not exists tax_resident boolean;
comment on column public.seller_profiles.tax_resident is
  'Tax residency declared by the seller (/join or profile completion), editable by the admin.
   NULL = unknown: withheld at the non-resident (higher) rate.';

-- Backfill from the application the profile-completion page reads (in-app row first, else the
-- latest /join row linked to the seller), once the seller has submitted it.
update public.seller_profiles sp
   set tax_resident = a.tax_resident
  from (
    select distinct on (seller_profile_id) seller_profile_id, tax_resident, status
    from public.onboarding_applications
    where seller_profile_id is not null
    order by seller_profile_id, (source = 'existing_seller') desc, created_at desc
  ) a
 where a.seller_profile_id = sp.id
   and a.status in ('submitted', 'approved')
   and sp.tax_resident is null;

-- 3. Per-order snapshot (NULL = not computed yet)
alter table public.orders
  add column if not exists wh_category    text,
  add column if not exists wh_resident    boolean,
  add column if not exists wh_base        numeric,
  add column if not exists wh_vat_rate    numeric,
  add column if not exists wh_vat_amount  numeric,
  add column if not exists wh_pit_rate    numeric,
  add column if not exists wh_pit_amount  numeric,
  add column if not exists wh_computed_at timestamptz;
comment on column public.orders.wh_base is
  'Seller tax withholding snapshot (compute_order_withholding): base = subtotal (food, no delivery fee).
   wh_vat_amount / wh_pit_amount = whole VND on the part of the base above annual_revenue_threshold.
   Written once; later rate changes do not touch it.';

-- A payout's withholding is no longer one rate.
alter table public.admin_payouts alter column withholding_rate drop not null;
alter table public.admin_payouts alter column withholding_rate drop default;

-- 4. Compute one order. Idempotent: an order already computed is returned unchanged.
create or replace function public.compute_order_withholding(p_order_id uuid)
returns jsonb
language plpgsql
as $$
declare
  v_order     public.orders%rowtype;
  v_category  text;
  v_resident  boolean;
  v_vat_rate  numeric;
  v_pit_rate  numeric;
  v_threshold numeric;
  v_year_from timestamptz;
  v_year_to   timestamptz;
  v_before    numeric;
  v_taxable   numeric;
begin
  select * into v_order from public.orders where id = p_order_id for update;
  if not found then
    raise exception 'compute_order_withholding: order % not found', p_order_id;
  end if;

  if v_order.wh_computed_at is null then
    if v_order.payment_status is distinct from 'paid' then
      raise exception 'compute_order_withholding: order % is not paid', p_order_id;
    end if;

    -- One order per seller at a time: the year-to-date sum must include the previous order.
    perform pg_advisory_xact_lock(hashtext('compute_order_withholding:' || v_order.seller_id::text));

    select tax_category, tax_resident into v_category, v_resident
    from public.seller_profiles where id = v_order.seller_id;
    if v_category is null then
      raise exception 'compute_order_withholding: seller of order % not found', p_order_id;
    end if;

    select rate into v_vat_rate from public.admin_tax_config where key = 'wh_vat_' || v_category;
    select rate into v_pit_rate from public.admin_tax_config
     where key = 'wh_pit_' || v_category || case when v_resident then '_resident' else '_nonresident' end;
    select rate into v_threshold from public.admin_tax_config where key = 'annual_revenue_threshold';
    if v_vat_rate is null or v_pit_rate is null or v_threshold is null then
      raise exception 'compute_order_withholding: admin_tax_config missing a rate for category % (resident %) or annual_revenue_threshold',
        v_category, v_resident;
    end if;

    -- Revenue already computed this calendar year (Vietnam time, by payment time), cancelled
    -- orders left out. Only the part of this order above the threshold is taxed.
    v_year_from := date_trunc('year', coalesce(v_order.paid_at, now()) at time zone 'Asia/Ho_Chi_Minh')
                   at time zone 'Asia/Ho_Chi_Minh';
    v_year_to   := (date_trunc('year', coalesce(v_order.paid_at, now()) at time zone 'Asia/Ho_Chi_Minh') + interval '1 year')
                   at time zone 'Asia/Ho_Chi_Minh';
    select coalesce(sum(wh_base), 0) into v_before
    from public.orders
    where seller_id = v_order.seller_id
      and id <> p_order_id
      and wh_computed_at is not null
      and status not in ('cancelled', 'delivery_failed')
      and coalesce(paid_at, wh_computed_at) >= v_year_from
      and coalesce(paid_at, wh_computed_at) <  v_year_to;

    v_taxable := least(v_order.subtotal, greatest(0, v_before + v_order.subtotal - v_threshold));

    update public.orders
       set wh_category    = v_category,
           wh_resident    = v_resident,
           wh_base        = v_order.subtotal,
           wh_vat_rate    = v_vat_rate,
           wh_vat_amount  = round(v_taxable * v_vat_rate, 0),  -- half away from zero = half up here
           wh_pit_rate    = v_pit_rate,
           wh_pit_amount  = round(v_taxable * v_pit_rate, 0),
           wh_computed_at = now()
     where id = p_order_id
    returning * into v_order;
  end if;

  return jsonb_build_object(
    'order_id', v_order.id, 'wh_category', v_order.wh_category, 'wh_resident', v_order.wh_resident,
    'wh_base', v_order.wh_base, 'wh_vat_rate', v_order.wh_vat_rate, 'wh_vat_amount', v_order.wh_vat_amount,
    'wh_pit_rate', v_order.wh_pit_rate, 'wh_pit_amount', v_order.wh_pit_amount,
    'wh_computed_at', v_order.wh_computed_at);
end;
$$;

revoke execute on function public.compute_order_withholding(uuid) from public, anon, authenticated;
grant execute on function public.compute_order_withholding(uuid) to service_role;

-- 5. Payouts. Body = 20261020030000 except the withholding (steps 3-4) and the signature.
drop function if exists public.admin_generate_payout_for_seller(uuid, date, date, numeric, numeric, numeric);

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

-- Old signature: the admin app deployed before this change still passes the threshold and two
-- rates. They are ignored. Drop once the admin app calls the 2-param version everywhere.
create or replace function public.admin_generate_payouts(
  p_period_start date, p_period_end date,
  p_threshold numeric, p_rate_goods numeric, p_rate_services numeric
) returns jsonb
language sql
as $$ select public.admin_generate_payouts(p_period_start, p_period_end) $$;

revoke execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric)
  from public, anon, authenticated;
grant execute on function public.admin_generate_payouts(date, date, numeric, numeric, numeric) to service_role;
