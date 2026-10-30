begin;
-- G4 update_order_payment_status (20261016010000) and the orders triggers: set_order_status_changed_at
-- (20261015020000), log_order_status (20261016030000). The IPN guard (a paid order never goes back to
-- failed) is in Python, apis/payments.py, not in this function: tests/backend covers it.
\ir _fixtures.sql

select pg_temp.t_seller('g4') as s \gset
select pg_temp.t_order(:'s', 100000, p_status => 'pending', p_paid_at => null, p_done_at => '2026-09-01 10:00+07') as o \gset
insert into payments (order_id, method, amount, status, type) values (:'o', 'vnpay', 100000, 'pending', 'charge');

-- TC-7: an insert logs its status once.
select pg_temp.expect('TC-7 insert logged', 1::bigint, (select count(*) from history_order_status where order_id = :'o'));

-- TC-7 / TC-34: paid sets paid_at and the ref, on the payment row too.
select update_order_payment_status(:'o', 'paid', 'TEST-REF-1');
select pg_temp.expect('TC-7 paid', 'paid', (select payment_status from orders where id = :'o'));
select pg_temp.expect('TC-7 paid_at', now(), (select paid_at from orders where id = :'o'));
select pg_temp.expect('TC-7 payment row', 'paid', (select status from payments where order_id = :'o'));
select pg_temp.expect('TC-7 payment ref', 'TEST-REF-1', (select transaction_ref from payments where order_id = :'o'));
-- paid again (IPN retry): paid_at keeps its first value, a missing ref keeps the old one.
update orders set paid_at = '2026-09-01 10:00+07' where id = :'o';
select update_order_payment_status(:'o', 'paid');
select pg_temp.expect('TC-34 paid_at kept', '2026-09-01 10:00+07'::timestamptz, (select paid_at from orders where id = :'o'));
select pg_temp.expect('TC-34 ref kept', 'TEST-REF-1', (select transaction_ref from orders where id = :'o'));
-- a payment change is not a status change: no history line, status_changed_at unchanged
select pg_temp.expect('TC-34 no history for payment', 1::bigint, (select count(*) from history_order_status where order_id = :'o'));
select pg_temp.expect('TC-34 status_changed_at kept', '2026-09-01 10:00+07'::timestamptz, (select status_changed_at from orders where id = :'o'));

-- TC-7: each status change: one history line, status_changed_at = now; same status again: nothing.
update orders set status = 'confirmed' where id = :'o';
select pg_temp.expect('TC-7 confirmed logged', 2::bigint, (select count(*) from history_order_status where order_id = :'o'));
select pg_temp.expect('TC-7 status_changed_at', now(), (select status_changed_at from orders where id = :'o'));
update orders set status_changed_at = '2026-09-01 11:00+07' where id = :'o';
update orders set status = 'confirmed' where id = :'o';
select pg_temp.expect('TC-7 same status not logged', 2::bigint, (select count(*) from history_order_status where order_id = :'o'));
select pg_temp.expect('TC-7 same status keeps time', '2026-09-01 11:00+07'::timestamptz, (select status_changed_at from orders where id = :'o'));

-- TC-35: nothing on orders reaches outside the database (no pg_net / http / notify / dblink).
select pg_temp.expect('TC-35 extensions', 0::bigint,
  (select count(*) from pg_extension where extname in ('pg_net', 'http', 'dblink')));
select pg_temp.expect('TC-35 functions', 0::bigint,
  (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.prosrc ~* '\mnet\.|pg_notify|\mhttp_|dblink'));

rollback;
