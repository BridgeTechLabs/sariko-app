begin;
-- G9 admin_close_cancelled_order_deductions (T174 A1, docs/dev/20261110-payout-fixes, migration 20261110170312): a
-- payout cancelled or failed closes the "Charge to seller" deduction of each of its cancelled orders (never paid):
-- nothing taken elsewhere -> deleted ('removed'); already taken by another payout -> stops there ('stopped').
-- Deductions of other orders, of orders still done and monthly fees stay; a completed payout closes nothing.
\ir _fixtures.sql

select pg_temp.t_setting('complaint_window_hours', '24');
select pg_temp.t_setting('payout_deduction_max_percent', '100');
select pg_temp.t_setting('fee_start_date', '99991231');   -- no monthly fee of its own: the test makes one

select pg_temp.t_seller('g9') as s \gset
do $$
declare
  s     uuid := (select id from seller_profiles where store_name = 'TEST sql g9');
  r     jsonb;
  p     uuid;   -- the payout cancelled / failed
  p2    uuid;   -- a later payout of the same store
  o1    uuid;   -- done order in p, then cancelled + "Charge to seller"
  o2    uuid;   -- done order in p, stays done
  d1    uuid;   -- deduction of o1
  d2    uuid;   -- deduction of o2: never closed
  dx    uuid;   -- deduction of an order outside p
  df    uuid;   -- monthly fee
begin
  o1 := pg_temp.t_order(s, 100000, p_wh_vat => 0, p_wh_pit => 0);
  o2 := pg_temp.t_order(s, 50000, p_wh_vat => 0, p_wh_pit => 0);
  r := admin_generate_payout_for_seller(s, '2026-08-31', '2026-09-06');
  p := (r->'payout'->>'id')::uuid;
  perform pg_temp.expect('setup payout', 'created', r->>'status');
  update orders set status = 'cancelled' where id = o1;
  insert into admin_payout_deductions (seller_id, order_id, amount, reason) values (s, o1, 100000, 'TEST sql g9') returning id into d1;
  insert into admin_payout_deductions (seller_id, order_id, amount, reason) values (s, o2, 2000, 'TEST sql g9') returning id into d2;
  insert into admin_payout_deductions (seller_id, order_id, amount, reason) values (s, gen_random_uuid(), 7000, 'TEST sql g9') returning id into dx;
  insert into admin_payout_deductions (seller_id, amount, reason, fee_month) values (s, 3000, 'TEST sql g9', '2026-09-01') returning id into df;

  -- TC-A1a (cancel): d1 deleted, reported 'removed'; d2, dx, df untouched
  r := admin_cancel_payout(p, 'TEST sql');
  perform pg_temp.expect('TC-A1a cancel ok', 'ok', r->>'status');
  perform pg_temp.expect('TC-A1a d1 deleted', false, exists (select 1 from admin_payout_deductions where id = d1));
  perform pg_temp.expect('TC-A1a reported', '[{"action": "removed", "amount": 100000, "taken": 0}]'::jsonb,
    (select jsonb_agg(e - 'deduction_id' - 'order_id' - 'seller_id') from jsonb_array_elements(r->'deductions_closed') e));
  perform pg_temp.expect('TC-A1a others open', 3::bigint,
    (select count(*) from admin_payout_deductions where id in (d2, dx, df) and applied_amount = 0));
  -- TC-A1c: a second cancel answers an error and changes nothing
  perform pg_temp.expect('TC-A1c second cancel', 'not_pending', admin_cancel_payout(p, 'TEST sql')->>'reason');
  delete from admin_payout_deductions where id = d2;

  -- TC-A1a (failed): a new payout of o2 (o1 cancelled is not taken again); o1 placed back in it as before its cancel
  r := admin_generate_payout_for_seller(s, '2026-08-30', '2026-09-06');
  p := (r->'payout'->>'id')::uuid;
  update orders set payout_id = p, payout_status = 'processing' where id = o1;
  insert into admin_payout_deductions (seller_id, order_id, amount, reason) values (s, o1, 100000, 'TEST sql g9') returning id into d1;
  r := admin_update_payout_status(p, 'failed');
  perform pg_temp.expect('TC-A1a failed ok', 'ok', r->>'status');
  perform pg_temp.expect('TC-A1a failed d1 deleted', false, exists (select 1 from admin_payout_deductions where id = d1));
  perform pg_temp.expect('TC-A1a failed reported', 1, jsonb_array_length(r->'deductions_closed'));

  -- TC-A1b: a completed payout closes nothing (the store was paid for the order)
  r := admin_generate_payout_for_seller(s, '2026-08-29', '2026-09-06');
  p := (r->'payout'->>'id')::uuid;
  update orders set payout_id = p, payout_status = 'processing' where id = o1;
  perform admin_update_payout_status(p, 'processing');
  r := admin_update_payout_status(p, 'completed');
  perform pg_temp.expect('TC-A1b completed closes nothing', '[]'::jsonb, r->'deductions_closed');

  -- TC-A1d: o1 in a payout p that will fail; its deduction d1 (300.000) is first taken in part by a later payout p2
  -- (an order of 80.000; dx and df were taken by the completed payout above) -> 80.000 of d1. p fails -> d1 stops at 80.000.
  update orders set payout_id = null, payout_status = 'pending', status = 'done' where id = o1;
  update orders set status_changed_at = '2026-09-03 10:00+07' where id = o1;   -- the status trigger set now()
  r := admin_generate_payout_for_seller(s, '2026-08-28', '2026-09-06');
  p := (r->'payout'->>'id')::uuid;
  perform pg_temp.expect('TC-A1d setup payout', 'created', r->>'status');
  update orders set status = 'cancelled' where id = o1;
  insert into admin_payout_deductions (seller_id, order_id, amount, reason, created_at)
    values (s, o1, 300000, 'TEST sql g9', '2026-09-10') returning id into d1;
  perform pg_temp.t_order(s, 80000, p_wh_vat => 0, p_wh_pit => 0, p_done_at => '2026-09-10 10:00+07');
  r := admin_generate_payout_for_seller(s, '2026-09-07', '2026-09-13');
  p2 := (r->'payout'->>'id')::uuid;
  perform pg_temp.expect('TC-A1d setup: p2 took', 80000::numeric, (select applied_amount from admin_payout_deductions where id = d1));
  r := admin_update_payout_status(p, 'failed');
  perform pg_temp.expect('TC-A1d amount', 80000::numeric, (select amount from admin_payout_deductions where id = d1));
  perform pg_temp.expect('TC-A1d applied', 80000::numeric, (select applied_amount from admin_payout_deductions where id = d1));
  perform pg_temp.expect('TC-A1d reported', 'stopped', r->'deductions_closed'->0->>'action');
  perform pg_temp.expect('TC-A1d taken', 80000::numeric, (r->'deductions_closed'->0->>'taken')::numeric);
  perform pg_temp.expect('TC-A1d p2 untouched', true,
    exists (select 1 from admin_payout_deduction_applications where payout_id = p2 and deduction_id = d1 and amount = 80000));
end $$;

-- only the admin backend (service role) may call the new function
select pg_temp.expect('TC-A1 anon cannot call', false, has_function_privilege('anon', 'public.admin_close_cancelled_order_deductions(uuid)', 'execute'));
select pg_temp.expect('TC-A1 authenticated cannot call', false, has_function_privilege('authenticated', 'public.admin_close_cancelled_order_deductions(uuid)', 'execute'));

rollback;
