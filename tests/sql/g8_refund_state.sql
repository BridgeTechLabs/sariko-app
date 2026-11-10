begin;
-- G8 refund_state(orders) (T172, docs/dev/20261110-refund-state): the order's MAIN refund (reason other than
-- duplicate_payment, at most one per order: refunds_order_id_key) as null | in_progress | failed | refunded.
\ir _fixtures.sql

select pg_temp.t_seller('g8') as s \gset
select pg_temp.t_order(:'s', 100000, p_status => 'cancelled') as o \gset
create function pg_temp.t_refund(p_order uuid, p_reason text, p_status text, p_txn text default null) returns uuid
language sql as $$
  insert into public.refunds (order_id, amount, reason, status, original_txn_ref)
  values (p_order, 100000, p_reason, p_status, p_txn) returning id
$$;
create function pg_temp.state(p_order uuid) returns text language sql as $$
  select public.refund_state(o) from public.orders o where o.id = p_order
$$;

-- TC-1: no refund -> null; main refund pending -> in_progress, failed -> failed, processed -> refunded.
select pg_temp.expect('TC-1 no refund', null::text, pg_temp.state(:'o'));
select pg_temp.t_refund(:'o', 'seller_cancel', 'pending') as r \gset
select pg_temp.expect('TC-1 pending', 'in_progress', pg_temp.state(:'o'));
-- TC-16: pending -> failed -> processed (an admin retry)
update public.refunds set status = 'failed' where id = :'r';
select pg_temp.expect('TC-16 failed', 'failed', pg_temp.state(:'o'));
update public.refunds set status = 'processed' where id = :'r';
select pg_temp.expect('TC-16 processed', 'refunded', pg_temp.state(:'o'));

-- TC-17 / TC-2: duplicate_payment rows never decide it, whatever their status.
select pg_temp.t_refund(:'o', 'duplicate_payment', 'pending', 'TEST-DUP-1');
select pg_temp.t_refund(:'o', 'duplicate_payment', 'processed', 'TEST-DUP-2');
select pg_temp.expect('TC-17 main processed + 2 duplicates', 'refunded', pg_temp.state(:'o'));
select pg_temp.t_order(:'s', 100000, p_status => 'done') as d \gset
select pg_temp.t_refund(:'d', 'duplicate_payment', 'pending', 'TEST-DUP-3');
select pg_temp.expect('TC-2 duplicate only', null::text, pg_temp.state(:'d'));

-- The rule leans on "one main refund per order": the partial unique index refuses a second one.
select pg_temp.expect_error('TC-17 one main refund', format($q$select pg_temp.t_refund(%L, 'admin_cancel', 'pending')$q$, :'o'),
  '%refunds_order_id_key%');

-- TC-11: stable, SECURITY INVOKER, one argument of type orders; only the service role may call it.
select pg_temp.expect('TC-11 stable', 's'::"char", (select provolatile from pg_proc where oid = 'public.refund_state(public.orders)'::regprocedure));
select pg_temp.expect('TC-11 invoker', false, (select prosecdef from pg_proc where oid = 'public.refund_state(public.orders)'::regprocedure));
select pg_temp.expect('TC-11 anon cannot call', false, has_function_privilege('anon', 'public.refund_state(public.orders)', 'execute'));
select pg_temp.expect('TC-11 authenticated cannot call', false, has_function_privilege('authenticated', 'public.refund_state(public.orders)', 'execute'));
select pg_temp.expect('TC-11 service_role calls', true, has_function_privilege('service_role', 'public.refund_state(public.orders)', 'execute'));

rollback;
