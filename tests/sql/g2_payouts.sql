begin;
-- G2 admin_generate_payout_for_seller / admin_generate_payouts / admin_payout_done_before
-- (20261026000000_payout_auto.sql). A payout sums the orders' snapshot columns (payout_amount is set by the
-- app: subtotal - commission - VAT on the commission, delivery fee not in it) of paid, done, not held orders
-- that became done in the period (Vietnam days) and before the complaint window closed; withholding is the
-- orders' wh_* (capped at gross); open deductions are taken up to payout_deduction_max_percent of the net.
\ir _fixtures.sql

select pg_temp.t_setting('complaint_window_hours', '24');
select pg_temp.t_setting('payout_deduction_max_percent', '100');
select pg_temp.t_setting('fee_start_date', '99991231');  -- no monthly fee in this file (G6 covers it)

-- TC-2 / TC-25: 3 orders done in 01..07/09/2026. Snapshots (commission 17%, VAT 10% of the commission):
--   o1 delivery 100.000 + fee 20.000: commission 17.000, VAT 1.700, payout 81.300, no withholding
--   o2 pickup   200.000: commission 34.000, VAT 3.400, payout 162.600, withholding 600 + 300
--   o3 pickup    50.000: commission  8.500, VAT   850, payout  40.650
-- gross = 81.300 + 162.600 + 40.650 = 284.550 (the 20.000 fee is not in it); net = 284.550 - 900 = 283.650.
select pg_temp.t_seller('g2 main') as p1 \gset
select pg_temp.t_order(:'p1', 100000, p_commission => 17000, p_vat => 1700, p_delivery_fee => 20000, p_wh_vat => 0, p_wh_pit => 0) as o1 \gset
select pg_temp.t_order(:'p1', 200000, p_commission => 34000, p_vat => 3400, p_wh_vat => 600, p_wh_pit => 300) as o2 \gset
select pg_temp.t_order(:'p1', 50000, p_commission => 8500, p_vat => 850, p_wh_vat => 0, p_wh_pit => 0) as o3 \gset
select admin_generate_payout_for_seller(:'p1', '2026-09-01', '2026-09-07') as r \gset
select pg_temp.expect('TC-2 status', 'created', (:'r'::jsonb)->>'status');
select id as pay1 from admin_payouts where seller_id = :'p1' \gset
select pg_temp.expect('TC-2 order_count', 3, (select order_count from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 subtotal', 350000::numeric, (select total_subtotal from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 commission', 59500::numeric, (select total_commission from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 vat', 5950::numeric, (select total_vat from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-25 gross without delivery fee', 284550::numeric, (select gross_payout from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 withholding', 900::numeric, (select withholding_amount from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 net', 283650::numeric, (select net_payout from admin_payouts where id = :'pay1'));
select pg_temp.expect('TC-2 orders stamped', 3::bigint, (select count(*) from orders where payout_id = :'pay1' and payout_status = 'processing'));

-- TC-3: a second run for the same period makes nothing and counts nothing twice.
select pg_temp.expect('TC-3 skipped', 'payout_exists', (select admin_generate_payout_for_seller(:'p1', '2026-09-01', '2026-09-07')->>'reason'));
select pg_temp.expect('TC-3 one payout', 1::bigint, (select count(*) from admin_payouts where seller_id = :'p1'));

-- TC-22: Vietnam-day edges of 01..07/09: start day 00:00:00 and end day 23:59:59 in, the day after 00:00:00
-- and the day before 23:59:59 out. Amounts 1.000 / 2.000 / 4.000 / 8.000 tell them apart: gross 3.000.
select pg_temp.t_seller('g2 edges') as p2 \gset
select pg_temp.t_order(:'p2', 1000, p_done_at => '2026-09-01 00:00:00+07', p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p2', 2000, p_done_at => '2026-09-07 23:59:59+07', p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p2', 4000, p_done_at => '2026-09-08 00:00:00+07', p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p2', 8000, p_done_at => '2026-08-31 23:59:59+07', p_wh_vat => 0, p_wh_pit => 0);
select admin_generate_payout_for_seller(:'p2', '2026-09-01', '2026-09-07');
select pg_temp.expect('TC-22 count', 2, (select order_count from admin_payouts where seller_id = :'p2'));
select pg_temp.expect('TC-22 gross', 3000::numeric, (select gross_payout from admin_payouts where seller_id = :'p2'));

-- TC-23: the period ends at the end of its last Vietnam day, or earlier while the complaint window
-- (complaint_window_hours) is still open on orders done within it.
select pg_temp.expect('TC-23 past period', '2026-09-08 00:00+07'::timestamptz, admin_payout_done_before('2026-09-07'));
select pg_temp.t_setting('complaint_window_hours', '48');
select pg_temp.expect('TC-23 open window', now() - interval '48 hours', admin_payout_done_before(current_date + 1));
select pg_temp.t_setting('complaint_window_hours', '"x"');  -- invalid -> 24
select pg_temp.expect('TC-23 invalid setting', now() - interval '24 hours', admin_payout_done_before(current_date + 1));
select pg_temp.t_setting('complaint_window_hours', '48');
select pg_temp.t_seller('g2 window') as p3 \gset
select pg_temp.t_order(:'p3', 1000, p_done_at => now() - interval '47 hours', p_wh_vat => 0, p_wh_pit => 0);  -- still open
select pg_temp.t_order(:'p3', 2000, p_done_at => now() - interval '49 hours', p_wh_vat => 0, p_wh_pit => 0);  -- closed
select admin_generate_payout_for_seller(:'p3', current_date - 10, current_date + 1);
select pg_temp.expect('TC-23 only closed orders', 2000::numeric, (select gross_payout from admin_payouts where seller_id = :'p3'));
select pg_temp.t_setting('complaint_window_hours', '24');

-- TC-24: held, already in another payout, already paid out, not paid, not done: none counted. Only 16.000.
select pg_temp.t_seller('g2 excluded') as p4 \gset
insert into admin_payouts (seller_id, period_start, period_end, status) values (:'p4', '2026-08-01', '2026-08-07', 'pending')
returning id as other_payout \gset
select pg_temp.t_order(:'p4', 1000, p_wh_vat => 0, p_wh_pit => 0) as held \gset
update orders set payout_hold = true where id = :'held';
select pg_temp.t_order(:'p4', 2000, p_wh_vat => 0, p_wh_pit => 0) as taken \gset
update orders set payout_status = 'processing', payout_id = :'other_payout' where id = :'taken';
select pg_temp.t_order(:'p4', 4000, p_wh_vat => 0, p_wh_pit => 0) as paid_out \gset
update orders set payout_status = 'paid_out' where id = :'paid_out';
select pg_temp.t_order(:'p4', 8000, p_paid_at => null, p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p4', 32000, p_status => 'ready', p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p4', 16000, p_wh_vat => 0, p_wh_pit => 0);
select admin_generate_payout_for_seller(:'p4', '2026-09-01', '2026-09-07');
select pg_temp.expect('TC-24 count', 1, (select order_count from admin_payouts where seller_id = :'p4' and period_start = '2026-09-01'));
select pg_temp.expect('TC-24 gross', 16000::numeric, (select gross_payout from admin_payouts where seller_id = :'p4' and period_start = '2026-09-01'));
select pg_temp.expect('TC-24 held stays out', 'pending', (select payout_status from orders where id = :'held'));

-- TC-27: deduction 150.000 open, net 100.000, max 60% -> takes 60.000 now, 90.000 waits.
select pg_temp.t_setting('payout_deduction_max_percent', '60');
select pg_temp.t_seller('g2 deduction') as p5 \gset
select pg_temp.t_order(:'p5', 100000, p_wh_vat => 0, p_wh_pit => 0) as o5 \gset
insert into admin_payout_deductions (seller_id, order_id, amount, reason, created_by)
values (:'p5', :'o5', 150000, 'TEST sql refund', 'TEST sql') returning id as d5 \gset
select admin_generate_payout_for_seller(:'p5', '2026-09-01', '2026-09-07');
select id as pay5 from admin_payouts where seller_id = :'p5' \gset
select pg_temp.expect('TC-27 deducted', 60000::numeric, (select total_deductions from admin_payouts where id = :'pay5'));
select pg_temp.expect('TC-27 net', 40000::numeric, (select net_payout from admin_payouts where id = :'pay5'));
select pg_temp.expect('TC-27 applied', 60000::numeric, (select applied_amount from admin_payout_deductions where id = :'d5'));
select pg_temp.expect('TC-27 one application', 1::bigint, (select count(*) from admin_payout_deduction_applications where deduction_id = :'d5'));
select pg_temp.t_setting('payout_deduction_max_percent', '100');

-- TC-30: cancel, then make the same period again: the orders come back once, the deduction is returned
-- then taken again (max now 100%: 100.000 of the 150.000).
select admin_cancel_payout(:'pay5', 'TEST sql');
select pg_temp.expect('TC-30 returned', 0::numeric, (select applied_amount from admin_payout_deductions where id = :'d5'));
select pg_temp.expect('TC-30 recreated', 'created', (select admin_generate_payout_for_seller(:'p5', '2026-09-01', '2026-09-07')->>'status'));
select pg_temp.expect('TC-30 orders once', 1, (select order_count from admin_payouts where seller_id = :'p5' and status = 'pending'));
select pg_temp.expect('TC-30 retaken', 100000::numeric, (select applied_amount from admin_payout_deductions where id = :'d5'));
select pg_temp.expect('TC-30 net', 0::numeric, (select net_payout from admin_payouts where seller_id = :'p5' and status = 'pending'));

-- TC-28: withholding above gross is capped: payout 1.000, withholding 800 + 400 -> 1.000, net 0, short 200.
select pg_temp.t_seller('g2 cap') as p6 \gset
select pg_temp.t_order(:'p6', 1000, p_wh_vat => 800, p_wh_pit => 400);
select admin_generate_payout_for_seller(:'p6', '2026-09-01', '2026-09-07') as r6 \gset
select pg_temp.expect('TC-28 withholding', 1000::numeric, (select withholding_amount from admin_payouts where seller_id = :'p6'));
select pg_temp.expect('TC-28 net', 0::numeric, (select net_payout from admin_payouts where seller_id = :'p6'));
select pg_temp.expect('TC-28 shortfall', 200::numeric, ((:'r6'::jsonb)->>'withholding_shortfall')::numeric);

-- TC-29: the batch over 01..07/06/2026. A store whose withholding can't be computed (no rate) is listed in
-- errors and keeps nothing; the other store is created; a store with no eligible order gets no payout.
select pg_temp.t_seller('g2 batch ok') as p7 \gset
select pg_temp.t_seller('g2 batch broken', p_category => 'services') as p8 \gset
select pg_temp.t_seller('g2 batch empty') as p9 \gset
select pg_temp.t_order(:'p7', 5000, p_done_at => '2026-06-03 10:00+07', p_wh_vat => 0, p_wh_pit => 0);
select pg_temp.t_order(:'p8', 5000, p_paid_at => '2026-06-02 10:00+07', p_done_at => '2026-06-03 10:00+07') as o8 \gset
select pg_temp.t_order(:'p9', 5000, p_status => 'cancelled', p_done_at => '2026-06-03 10:00+07', p_wh_vat => 0, p_wh_pit => 0);
delete from admin_tax_config where key = 'wh_vat_services';
select admin_generate_payouts('2026-06-01', '2026-06-07') as batch \gset
select pg_temp.expect('TC-29 ok store created', 1::bigint, (select count(*) from admin_payouts where seller_id = :'p7'));
select pg_temp.expect('TC-29 broken store listed', true,
  exists (select 1 from jsonb_array_elements((:'batch'::jsonb)->'errors') e where e->>'seller_id' = :'p8'));
select pg_temp.expect('TC-29 broken store keeps nothing', 0::bigint, (select count(*) from admin_payouts where seller_id = :'p8'));
select pg_temp.expect('TC-29 broken order untouched', 'pending', (select payout_status from orders where id = :'o8'));
select pg_temp.expect('TC-29 empty store no payout', 0::bigint, (select count(*) from admin_payouts where seller_id = :'p9'));

rollback;
