begin;
-- G7 admin_purge_orders (20261021030000_review_tables.sql): deletes the orders of one store (or all) created
-- before purge_orders_before (Vietnam date, YYYYMMDD; not set = 99991231 = every order), with their refunds,
-- history, deductions and the unpaid payouts only they fill; refuses when a payout in scope is processing
-- or completed; dry_run only counts.
\ir _fixtures.sql

select pg_temp.t_setting('purge_orders_before', '20260601');

-- Store A: an old order (with refund, payment, history) and a new one. Store B: an old order in a pending
-- payout. Store C: an old order in a processing payout.
select pg_temp.t_seller('g7 a') as a \gset
select pg_temp.t_seller('g7 b') as b \gset
select pg_temp.t_seller('g7 c') as c \gset
-- created_at is UTC: 31/05 23:59:59 VN (before the cutoff day) and 01/06 00:00 VN (on it)
select pg_temp.t_order(:'a', 10000, p_created_at => '2026-05-31 16:59:59') as a_old \gset
select pg_temp.t_order(:'a', 10000, p_created_at => '2026-05-31 17:00:00') as a_new \gset
insert into refunds (order_id, amount, reason) values (:'a_old', 10000, 'seller_cancel');
insert into payments (order_id, method, amount, status, type) values (:'a_old', 'vnpay', 10000, 'paid', 'charge');
select pg_temp.t_order(:'b', 20000, p_created_at => '2026-05-01 03:00') as b_old \gset
insert into admin_payouts (seller_id, period_start, period_end, status) values (:'b', '2026-05-01', '2026-05-07', 'pending')
returning id as pay_b \gset
update orders set payout_status = 'processing', payout_id = :'pay_b' where id = :'b_old';
select pg_temp.t_order(:'c', 30000, p_created_at => '2026-05-01 03:00') as c_old \gset
insert into admin_payouts (seller_id, period_start, period_end, status) values (:'c', '2026-05-01', '2026-05-07', 'processing')
returning id as pay_c \gset
update orders set payout_status = 'processing', payout_id = :'pay_c' where id = :'c_old';

-- TC-42 dry run: counts, deletes nothing.
select admin_purge_orders(:'a', true, 'TEST sql') as dry \gset
select pg_temp.expect('TC-42 dry orders', 1, ((:'dry'::jsonb)->'counts'->>'orders')::int);
select pg_temp.expect('TC-42 dry refunds', 1, ((:'dry'::jsonb)->'counts'->>'refunds')::int);
select pg_temp.expect('TC-42 dry skipped', 1, ((:'dry'::jsonb)->>'skipped_after_cutoff')::int);
select pg_temp.expect('TC-42 dry deletes nothing', 2::bigint, (select count(*) from orders where seller_id = :'a'));

-- TC-10 / TC-42: real run on A: only A's old order and its rows go; A's new order, B and C stay.
select pg_temp.expect('TC-42 run', 'ok', admin_purge_orders(:'a', false, 'TEST sql')->>'status');
select pg_temp.expect('TC-10 A old gone', 0::bigint, (select count(*) from orders where id = :'a_old'));
select pg_temp.expect('TC-10 A refund gone', 0::bigint, (select count(*) from refunds where order_id = :'a_old'));
select pg_temp.expect('TC-10 A payment gone', 0::bigint, (select count(*) from payments where order_id = :'a_old'));
select pg_temp.expect('TC-10 A history gone', 0::bigint, (select count(*) from history_order_status where order_id = :'a_old'));
select pg_temp.expect('TC-42 A new kept', 1::bigint, (select count(*) from orders where id = :'a_new'));
select pg_temp.expect('TC-10 B kept', 1::bigint, (select count(*) from orders where id = :'b_old'));
select pg_temp.expect('TC-10 B payout kept', 1::bigint, (select count(*) from admin_payouts where id = :'pay_b'));
select pg_temp.expect('TC-10 C kept', 1::bigint, (select count(*) from orders where id = :'c_old'));
select pg_temp.expect('TC-42 logged', 1::bigint,
  (select count(*) from history_admin_actions where action = 'purge_orders' and actor = 'TEST sql' and params->>'seller_id' = :'a'));

-- B: its order and the pending payout only that order filled both go.
select admin_purge_orders(:'b', false, 'TEST sql');
select pg_temp.expect('TC-42 B order gone', 0::bigint, (select count(*) from orders where id = :'b_old'));
select pg_temp.expect('TC-42 B payout gone', 0::bigint, (select count(*) from admin_payouts where id = :'pay_b'));

-- TC-42: C's payout is being paid: refused, nothing deleted.
select pg_temp.expect('TC-42 locked', 'payout_locked', admin_purge_orders(:'c', false, 'TEST sql')->>'reason');
select pg_temp.expect('TC-42 locked kept', 1::bigint, (select count(*) from orders where id = :'c_old'));

-- Not set: 99991231, every order of the store (A's new one too).
delete from admin_settings where key = 'purge_orders_before';
select pg_temp.expect('TC-42 no cutoff = all', 1, (admin_purge_orders(:'a', true, 'TEST sql')->'counts'->>'orders')::int);

-- TC-43: all stores, dry run only (a real run would lock every DEV order): deletes nothing.
select count(*) as all_before from orders \gset
select admin_purge_orders(null, true, 'TEST sql');
select pg_temp.expect('TC-43 dry all deletes nothing', :all_before::bigint, (select count(*) from orders));

rollback;
