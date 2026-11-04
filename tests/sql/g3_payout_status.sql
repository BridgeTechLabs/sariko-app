begin;
-- G3 admin_update_payout_status (20261016050000) / admin_cancel_payout (20261026000000): forward-only
-- pending -> processing | failed, processing -> completed | failed; every other move answers
-- {status: error, reason: invalid_transition} and changes nothing. completed marks the orders paid_out;
-- failed and cancel hand the orders and the deductions back for the next period.
\ir _fixtures.sql

select pg_temp.t_setting('complaint_window_hours', '24');
select pg_temp.t_setting('payout_deduction_max_percent', '100');
select pg_temp.t_setting('fee_start_date', '99991231');

-- TC-32: every pair, on bare payouts (no orders).
select pg_temp.t_seller('g3 matrix');
do $$
declare
  v_from text; v_to text; v_id uuid; v_ok boolean; v_res jsonb; v_week int := 0;
  v_seller uuid := (select id from seller_profiles where store_name = 'TEST sql g3 matrix');
begin
  foreach v_from in array array['pending', 'processing', 'completed', 'failed', 'cancelled'] loop
    foreach v_to in array array['pending', 'processing', 'completed', 'failed', 'cancelled'] loop
      v_week := v_week + 1;
      insert into admin_payouts (seller_id, period_start, period_end, status)
      values (v_seller, date '2025-01-01' + 7 * v_week, date '2025-01-07' + 7 * v_week, v_from)
      returning id into v_id;
      v_ok := (v_from, v_to) in (('pending', 'processing'), ('pending', 'failed'),
                                 ('processing', 'completed'), ('processing', 'failed'));
      v_res := admin_update_payout_status(v_id, v_to);
      if (v_res->>'status' = 'ok') is distinct from v_ok then
        raise exception 'TC-32 %->%: mong %, được %', v_from, v_to, (case when v_ok then 'ok' else 'invalid_transition' end), v_res;
      end if;
      if (select status from admin_payouts where id = v_id) <> (case when v_ok then v_to else v_from end) then
        raise exception 'TC-32 %->%: status in the table did not follow', v_from, v_to;
      end if;
    end loop;
  end loop;
end $$;

-- TC-5: pending -> processing -> completed on a real payout: orders paid_out, paid_at set;
-- completed -> pending refused.
select pg_temp.t_seller('g3 paid') as s1 \gset
select pg_temp.t_order(:'s1', 100000, p_wh_vat => 0, p_wh_pit => 0) as o1 \gset
select admin_generate_payout_for_seller(:'s1', '2026-09-01', '2026-09-07');
select id as pay1 from admin_payouts where seller_id = :'s1' \gset
select pg_temp.expect('TC-5 processing', 'ok', admin_update_payout_status(:'pay1', 'processing')->>'status');
select pg_temp.expect('TC-5 completed', 'ok', admin_update_payout_status(:'pay1', 'completed', 'TEST sql transfer')->>'status');
select pg_temp.expect('TC-5 order paid out', 'paid_out', (select payout_status from orders where id = :'o1'));
select pg_temp.expect('TC-5 paid_at', true, (select paid_at is not null from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-5 back refused', 'invalid_transition', admin_update_payout_status(:'pay1', 'pending')->>'reason');

-- TC-32 failed: orders back to pending without payout, the deduction's share returned, application gone.
select pg_temp.t_seller('g3 failed') as s2 \gset
select pg_temp.t_order(:'s2', 100000, p_wh_vat => 0, p_wh_pit => 0) as o2 \gset
insert into admin_payout_deductions (seller_id, order_id, amount, reason, created_by)
values (:'s2', :'o2', 30000, 'TEST sql refund', 'TEST sql') returning id as d2 \gset
select admin_generate_payout_for_seller(:'s2', '2026-09-01', '2026-09-07');
select id as pay2 from admin_payouts where seller_id = :'s2' \gset
select pg_temp.expect('TC-32 taken first', 30000::numeric, (select applied_amount from admin_payout_deductions where id = :'d2'));
select admin_update_payout_status(:'pay2', 'processing');
select admin_update_payout_status(:'pay2', 'failed');
select pg_temp.expect('TC-32 failed order', 'pending', (select payout_status from orders where id = :'o2'));
select pg_temp.expect('TC-32 failed payout_id', null::uuid, (select payout_id from orders where id = :'o2'));
select pg_temp.expect('TC-32 failed deduction', 0::numeric, (select applied_amount from admin_payout_deductions where id = :'d2'));
select pg_temp.expect('TC-32 failed applications', 0::bigint, (select count(*) from admin_payout_deduction_applications where payout_id = :'pay2'));
-- TC-4: the next period takes that order again, once.
select admin_generate_payout_for_seller(:'s2', '2026-09-01', '2026-09-14');
select pg_temp.expect('TC-4 order again', 1, (select order_count from admin_payouts where seller_id = :'s2' and period_end = '2026-09-14'));

-- TC-6 / TC-33: cancel only while pending. A pending one: cancelled_at / by set, orders and deduction back.
select pg_temp.t_seller('g3 cancel') as s3 \gset
select pg_temp.t_order(:'s3', 100000, p_wh_vat => 0, p_wh_pit => 0) as o3 \gset
insert into admin_payout_deductions (seller_id, order_id, amount, reason, created_by)
values (:'s3', :'o3', 30000, 'TEST sql refund', 'TEST sql') returning id as d3 \gset
select admin_generate_payout_for_seller(:'s3', '2026-09-01', '2026-09-07');
select id as pay3 from admin_payouts where seller_id = :'s3' \gset
select pg_temp.expect('TC-33 cancel', 'ok', admin_cancel_payout(:'pay3', 'TEST sql operator')->>'status');
select pg_temp.expect('TC-6 status', 'cancelled', (select status from admin_payouts where id = :'pay3'));
select pg_temp.expect('TC-33 cancelled_by', 'TEST sql operator', (select cancelled_by from admin_payouts where id = :'pay3'));
select pg_temp.expect('TC-33 cancelled_at', true, (select cancelled_at is not null from admin_payouts where id = :'pay3'));
select pg_temp.expect('TC-6 order back', 'pending', (select payout_status from orders where id = :'o3'));
select pg_temp.expect('TC-6 order unlinked', null::uuid, (select payout_id from orders where id = :'o3'));
select pg_temp.expect('TC-33 deduction back', 0::numeric, (select applied_amount from admin_payout_deductions where id = :'d3'));
select pg_temp.expect('TC-33 cancel twice', 'not_pending', admin_cancel_payout(:'pay3')->>'reason');
-- processing / completed refused, nothing moves
select admin_generate_payout_for_seller(:'s3', '2026-09-01', '2026-09-07');
select id as pay4 from admin_payouts where seller_id = :'s3' and status = 'pending' \gset
select admin_update_payout_status(:'pay4', 'processing');
select pg_temp.expect('TC-33 processing refused', 'not_pending', admin_cancel_payout(:'pay4')->>'reason');
select admin_update_payout_status(:'pay4', 'completed');
select pg_temp.expect('TC-33 completed refused', 'not_pending', admin_cancel_payout(:'pay4')->>'reason');
select pg_temp.expect('TC-33 completed kept', 'paid_out', (select payout_status from orders where id = :'o3'));

rollback;
