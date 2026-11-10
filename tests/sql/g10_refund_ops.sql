begin;
-- G10 refund ops (T175, docs/dev/20261110-refund-ops): duplicate_refund(orders) = the buyer's extra payments being
-- returned (A6), refunds.needs_check (A16) and admin_settings.refund_stuck_hours (A16).
\ir _fixtures.sql

select pg_temp.t_seller('g10') as s \gset
select pg_temp.t_order(:'s', 100000, p_status => 'done') as o \gset
create function pg_temp.t_refund(p_order uuid, p_reason text, p_status text, p_amount numeric, p_txn text default null)
returns uuid language sql as $$
  insert into public.refunds (order_id, amount, reason, status, original_txn_ref)
  values (p_order, p_amount, p_reason, p_status, p_txn) returning id
$$;
create function pg_temp.dup(p_order uuid) returns jsonb language sql as $$
  select public.duplicate_refund(o) from public.orders o where o.id = p_order
$$;

-- TC-A6a: no extra payment -> null; the main refund never counts.
select pg_temp.expect('TC-A6a none', null::jsonb, pg_temp.dup(:'o'));
select pg_temp.t_refund(:'o', 'seller_cancel', 'processed', 100000);
select pg_temp.expect('TC-A6a main refund only', null::jsonb, pg_temp.dup(:'o'));
-- two extra payments, one returned: the sum, still in progress; both returned: refunded. Whole VND.
select pg_temp.t_refund(:'o', 'duplicate_payment', 'pending', 100000, 'TEST-DUP-1') as d1 \gset
select pg_temp.t_refund(:'o', 'duplicate_payment', 'processed', 25000.4, 'TEST-DUP-2');
select pg_temp.expect('TC-A6a in progress', '{"amount": 125000, "state": "in_progress"}'::jsonb, pg_temp.dup(:'o'));
update public.refunds set status = 'failed' where id = :'d1';
select pg_temp.expect('TC-A6a failed is still on its way', 'in_progress', pg_temp.dup(:'o') ->> 'state');
update public.refunds set status = 'processed' where id = :'d1';
select pg_temp.expect('TC-A6a refunded', '{"amount": 125000, "state": "refunded"}'::jsonb, pg_temp.dup(:'o'));

-- Same rules as refund_state: stable, invoker, only the backends' service role calls it.
select pg_temp.expect('TC-A6a stable', 's'::"char", (select provolatile from pg_proc where oid = 'public.duplicate_refund(public.orders)'::regprocedure));
select pg_temp.expect('TC-A6a invoker', false, (select prosecdef from pg_proc where oid = 'public.duplicate_refund(public.orders)'::regprocedure));
select pg_temp.expect('TC-A6a anon', false, has_function_privilege('anon', 'public.duplicate_refund(public.orders)', 'execute'));
select pg_temp.expect('TC-A6a authenticated', false, has_function_privilege('authenticated', 'public.duplicate_refund(public.orders)', 'execute'));
select pg_temp.expect('TC-A6a service_role', true, has_function_privilege('service_role', 'public.duplicate_refund(public.orders)', 'execute'));

-- TC-A16a / A16b: the flag defaults to false; the setting exists with an English description.
select pg_temp.expect('TC-A16b needs_check default', false, (select needs_check from public.refunds where id = :'d1'));
-- Process claims the row before calling VNPay (QA race: Process vs "refunded by hand"); free by default
select pg_temp.expect('TC-A3 processing_at default', null::timestamptz, (select processing_at from public.refunds where id = :'d1'));
-- the key exists and is a whole number > 0; its value is the team's to change on DEV (QA: never pin 24 here)
select pg_temp.expect('TC-A16a refund_stuck_hours', true,
  (select jsonb_typeof(value) = 'number' and (value #>> '{}')::numeric > 0 and (value #>> '{}')::numeric % 1 = 0
     from public.admin_settings where key = 'refund_stuck_hours'));
select pg_temp.expect('TC-A16a description', true, (select description ~ '^[A-Z][ -~]+$' from public.admin_settings where key = 'refund_stuck_hours'));

rollback;
