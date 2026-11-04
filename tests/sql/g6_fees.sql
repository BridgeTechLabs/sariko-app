begin;
-- G6 admin_charge_monthly_fees (20261021080000_monthly_fee.sql): one deduction per store and month from
-- fee_start_date (or the store's first month, the later one) to this month (Vietnam time), at the plan's
-- monthly_fee_vnd; founding stores get founding_free_months first; a free plan is never charged.
-- lock_founding_commission (20261021000000): the founding plan's commission rate can't change.
\ir _fixtures.sql

-- Plan prices from the seller-onboarding design (750K / 1,25M), set here so DEV edits don't matter (TC-45).
update admin_tier_config set monthly_fee_vnd = 1250000 where tier = 'negosyo';
update admin_tier_config set monthly_fee_vnd = 750000 where tier = 'founding';
update admin_tier_config set monthly_fee_vnd = 0 where tier = 'community';
select pg_temp.t_setting('founding_free_months', '2');
-- fees start on the 1st of the month two months ago: this month and the two before are owed
select (date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh') - interval '2 months')::date as m0,
       (date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh') - interval '1 month')::date as m1,
       date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh')::date as m2 \gset
select pg_temp.t_setting('fee_start_date', to_jsonb(to_char(:'m0'::date, 'YYYYMMDD')::int));

-- TC-9 / TC-40: paid plan, store older than the start: 3 months x 1.250.000, fee_month the 1st of each.
select pg_temp.t_seller('g6 negosyo', p_tier => 'negosyo') as paid \gset
select pg_temp.expect('TC-40 charged', 3, admin_charge_monthly_fees(:'paid'));
select pg_temp.expect('TC-40 months', array[:'m0', :'m1', :'m2']::date[],
  (select array_agg(fee_month order by fee_month) from admin_payout_deductions where seller_id = :'paid'));
select pg_temp.expect('TC-40 amount', 3750000::numeric, (select sum(amount) from admin_payout_deductions where seller_id = :'paid'));
select pg_temp.expect('TC-40 reason', 'monthly_fee', (select min(reason) from admin_payout_deductions where seller_id = :'paid'));
-- TC-9: a second run in the same month charges nothing more
select pg_temp.expect('TC-9 second run', 0, admin_charge_monthly_fees(:'paid'));
select pg_temp.expect('TC-9 still 3', 3::bigint, (select count(*) from admin_payout_deductions where seller_id = :'paid'));

-- TC-40: founding: the first 2 months free, the third charged at 750.000.
select pg_temp.t_seller('g6 founding', p_tier => 'founding') as founding \gset
select pg_temp.expect('TC-40 founding', 1, admin_charge_monthly_fees(:'founding'));
select pg_temp.expect('TC-40 founding month', :'m2'::date, (select fee_month from admin_payout_deductions where seller_id = :'founding'));
select pg_temp.expect('TC-40 founding amount', 750000::numeric, (select amount from admin_payout_deductions where seller_id = :'founding'));

-- TC-40: free plan never charged; a store opened this month owes this month only.
select pg_temp.t_seller('g6 community') as free \gset
select pg_temp.expect('TC-40 free plan', 0, admin_charge_monthly_fees(:'free'));
select pg_temp.t_seller('g6 new', p_tier => 'negosyo', p_created_at => (now() at time zone 'UTC')::timestamp) as fresh \gset
select pg_temp.expect('TC-40 new store', 1, admin_charge_monthly_fees(:'fresh'));

-- fee_start_date not set to a date: nothing charged
select pg_temp.t_setting('fee_start_date', '"soon"');
select pg_temp.t_seller('g6 no start', p_tier => 'negosyo') as nostart \gset
select pg_temp.expect('TC-40 no start date', 0, admin_charge_monthly_fees(:'nostart'));

-- TC-41: the founding commission rate is locked; another plan's rate can change.
select pg_temp.expect_error('TC-41 founding locked',
  'update admin_tier_config set commission_rate = commission_rate + 0.01 where tier = ''founding''', '%founding commission is locked%');
update admin_tier_config set commission_rate = commission_rate + 0.01 where tier = 'negosyo';

rollback;
