-- Helpers for the g*.sql files (\ir'd right after their "begin;"). Everything lives in pg_temp or in
-- the test's own transaction, which rolls back: nothing is left on the database.
-- TEST rows are named "TEST sql ..." so run.sh can count them before / after.

set local client_min_messages = error;  -- the functions' own "raise warning" lines are expected noise here

-- A user (public.users is created by the on_auth_user_created trigger).
create function pg_temp.t_user(p_name text) returns uuid language sql as $$
  insert into auth.users (id, email, raw_user_meta_data, created_at, updated_at)
  values (gen_random_uuid(), 'test-sql-' || gen_random_uuid() || '@example.invalid',
          jsonb_build_object('fullname', 'TEST sql ' || p_name), now(), now())
  returning id
$$;

-- A store. created_at matters for the monthly fee only.
create function pg_temp.t_seller(p_name text, p_tier text default 'community',
                                 p_category text default 'goods_services', p_resident boolean default true,
                                 p_created_at timestamp default '2026-01-01')
returns uuid language sql as $$
  insert into public.seller_profiles (user_id, store_name, slug, tier, tax_category, tax_resident, created_at)
  values (pg_temp.t_user(p_name), 'TEST sql ' || p_name, 'test-sql-' || gen_random_uuid(),
          p_tier, p_category, p_resident, p_created_at)
  returning id
$$;

-- An order of a new buyer. Money columns are the app's snapshot (utils/pricing.py), given as is.
-- p_paid_at null = not paid. p_wh_vat / p_wh_pit given = withholding already computed at payment.
create function pg_temp.t_order(p_seller uuid, p_subtotal numeric,
                                p_status text default 'done',
                                p_paid_at timestamptz default '2026-09-02 10:00+07',
                                p_done_at timestamptz default '2026-09-03 10:00+07',
                                p_commission numeric default 0, p_vat numeric default 0,
                                p_payout numeric default null, p_delivery_fee numeric default 0,
                                p_wh_vat numeric default null, p_wh_pit numeric default null,
                                p_appointment timestamptz default null,
                                p_created_at timestamp default '2026-09-02 03:00')
returns uuid language sql as $$
  insert into public.orders (user_id, seller_id, total_amount, subtotal, commission_amount, vat_amount,
                             payout_amount, delivery_fee, delivery_method, status, payment_status, paid_at,
                             status_changed_at, wh_vat_amount, wh_pit_amount, wh_computed_at,
                             delivery_appointment, created_at, note)
  values (pg_temp.t_user('buyer'), p_seller, p_subtotal + p_delivery_fee, p_subtotal, p_commission, p_vat,
          coalesce(p_payout, p_subtotal - p_commission - p_vat), p_delivery_fee,
          case when p_delivery_fee > 0 then 'delivery' else 'pickup' end,
          p_status, case when p_paid_at is null then 'pending' else 'paid' end, p_paid_at,
          p_done_at, p_wh_vat, p_wh_pit, case when p_wh_vat is null then null else now() end,
          p_appointment, p_created_at, 'TEST sql')
  returning id
$$;

-- '<TC>: mong <want>, được <got>' when they differ (numeric compares exactly: 455 = 455.00).
create function pg_temp.expect(p_tc text, p_want anycompatible, p_got anycompatible) returns void
language plpgsql as $$
begin
  if p_got is distinct from p_want then
    raise exception '%: mong %, được %', p_tc, p_want, p_got;
  end if;
end $$;

-- The statement must fail with a message LIKE p_pattern; whatever it wrote is rolled back.
create function pg_temp.expect_error(p_tc text, p_stmt text, p_pattern text) returns void
language plpgsql as $$
begin
  begin
    execute p_stmt;
  exception when others then
    if sqlerrm like p_pattern then
      return;
    end if;
    raise exception '%: mong lỗi "%", được "%"', p_tc, p_pattern, sqlerrm;
  end;
  raise exception '%: mong lỗi "%", không có lỗi', p_tc, p_pattern;
end $$;

-- Business settings the tests depend on are set here, never assumed from DEV (TC-45).
create function pg_temp.t_setting(p_key text, p_value jsonb) returns void language sql as $$
  insert into public.admin_settings (key, value) values (p_key, p_value)
  on conflict (key) do update set value = excluded.value
$$;

create function pg_temp.t_tax(p_key text, p_rate numeric) returns void language sql as $$
  insert into public.admin_tax_config (key, rate) values (p_key, p_rate)
  on conflict (key) do update set rate = excluded.rate
$$;
