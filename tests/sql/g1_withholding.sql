begin;
-- G1 compute_order_withholding (20261021050000_tax_withholding.sql): tax only on the part of a store's
-- revenue for the calendar year (Vietnam time, by paid_at) above annual_revenue_threshold; cancelled /
-- delivery_failed orders left out; round half up to the đồng; computed once per order.
\ir _fixtures.sql

-- Rates set here (TC-45); every expected number below is worked out by hand from them.
select pg_temp.t_tax('annual_revenue_threshold', 1000000);
select pg_temp.t_tax('wh_vat_goods_services', 0.03);
select pg_temp.t_tax('wh_pit_goods_services_resident', 0.015);
select pg_temp.t_tax('wh_pit_goods_services_nonresident', 0.02);
select pg_temp.t_tax('wh_vat_goods', 0.045);
select pg_temp.t_tax('wh_pit_goods_resident', 0.005);

-- TC-14 / TC-15: resident store, goods_services.
select pg_temp.t_seller('g1 resident') as s1 \gset
select pg_temp.t_order(:'s1', 970000, p_paid_at => '2026-03-01 10:00+07') as o1 \gset
select pg_temp.t_order(:'s1', 100000, p_paid_at => '2026-03-02 10:00+07') as o2 \gset
select pg_temp.t_order(:'s1', 50000, p_paid_at => '2026-03-03 10:00+07') as o3 \gset

-- TC-14: 970.000 is all below the 1.000.000 threshold -> taxable 0.
select compute_order_withholding(:'o1');
select pg_temp.expect('TC-14 base', 970000::numeric, (select wh_base from orders where id = :'o1'));
select pg_temp.expect('TC-14 vat', 0::numeric, (select wh_vat_amount from orders where id = :'o1'));
select pg_temp.expect('TC-14 pit', 0::numeric, (select wh_pit_amount from orders where id = :'o1'));

-- TC-15: before 970.000 + 100.000 - 1.000.000 = 70.000 taxable; VAT 3% = 2.100, PIT 1,5% = 1.050.
select compute_order_withholding(:'o2');
select pg_temp.expect('TC-15 vat', 2100::numeric, (select wh_vat_amount from orders where id = :'o2'));
select pg_temp.expect('TC-15 pit', 1050::numeric, (select wh_pit_amount from orders where id = :'o2'));
-- next order: already above the threshold, all 50.000 taxable -> 1.500 + 750.
select compute_order_withholding(:'o3');
select pg_temp.expect('TC-15 next vat', 1500::numeric, (select wh_vat_amount from orders where id = :'o3'));
select pg_temp.expect('TC-15 next pit', 750::numeric, (select wh_pit_amount from orders where id = :'o3'));

-- TC-16: round half up. goods store, 1.010.100 alone -> taxable 10.100;
-- VAT 4,5% = 454,5 -> 455 (half up; half-even would give 454); PIT 0,5% = 50,5 -> 51.
select pg_temp.t_seller('g1 goods', p_category => 'goods') as s3 \gset
select pg_temp.t_order(:'s3', 1010100, p_paid_at => '2026-03-01 10:00+07') as o5 \gset
select compute_order_withholding(:'o5');
select pg_temp.expect('TC-16 vat', 455::numeric, (select wh_vat_amount from orders where id = :'o5'));
select pg_temp.expect('TC-16 pit', 51::numeric, (select wh_pit_amount from orders where id = :'o5'));

-- TC-17: non-resident, same category, 1.200.000 alone -> taxable 200.000;
-- VAT 3% = 6.000 (wh_vat_goods_services), PIT non-resident 2% = 4.000 (resident would be 3.000).
select pg_temp.t_seller('g1 nonresident', p_resident => false) as s2 \gset
select pg_temp.t_order(:'s2', 1200000, p_paid_at => '2026-03-01 10:00+07') as o4 \gset
select compute_order_withholding(:'o4');
select pg_temp.expect('TC-17 vat', 6000::numeric, (select wh_vat_amount from orders where id = :'o4'));
select pg_temp.expect('TC-17 pit', 4000::numeric, (select wh_pit_amount from orders where id = :'o4'));

-- TC-18: refused cases write nothing.
select pg_temp.t_order(:'s1', 300000, p_paid_at => null) as o_unpaid \gset
select pg_temp.expect_error('TC-18 unpaid', format('select compute_order_withholding(%L)', :'o_unpaid'), '%is not paid%');
select pg_temp.expect('TC-18 unpaid untouched', null::timestamptz, (select wh_computed_at from orders where id = :'o_unpaid'));
select pg_temp.expect_error('TC-18 not found', format('select compute_order_withholding(%L)', gen_random_uuid()), '%not found%');
select pg_temp.t_seller('g1 services', p_category => 'services') as s6 \gset
select pg_temp.t_order(:'s6', 300000, p_paid_at => '2026-03-01 10:00+07') as o_norate \gset
delete from admin_tax_config where key = 'wh_vat_services';
select pg_temp.expect_error('TC-18 missing rate', format('select compute_order_withholding(%L)', :'o_norate'), '%missing a rate%');
select pg_temp.expect('TC-18 missing rate untouched', null::timestamptz, (select wh_computed_at from orders where id = :'o_norate'));

-- TC-19: computed once. Rates change afterwards, a second call returns the stored numbers.
select pg_temp.t_tax('wh_vat_goods_services', 0.10);
select pg_temp.expect('TC-19 second call', 2100::numeric, (select (compute_order_withholding(:'o2')->>'wh_vat_amount')::numeric));
select pg_temp.expect('TC-19 stored', 2100::numeric, (select wh_vat_amount from orders where id = :'o2'));
select pg_temp.t_tax('wh_vat_goods_services', 0.03);

-- TC-20: the year is Vietnam time. A paid 31/12/2025 23:59:59 VN (16:59:59 UTC) is 2025 revenue:
-- 1.500.000 -> taxable 500.000. B paid 01/01/2026 00:00 VN (17:00 UTC on 31/12) starts 2026 from 0:
-- 800.000 -> taxable 0 (counted in UTC it would join 2025 and be taxed in full).
select pg_temp.t_seller('g1 new year') as s4 \gset
select pg_temp.t_order(:'s4', 1500000, p_paid_at => '2025-12-31 23:59:59+07') as o_a \gset
select pg_temp.t_order(:'s4', 800000, p_paid_at => '2026-01-01 00:00:00+07') as o_b \gset
select compute_order_withholding(:'o_a');
select compute_order_withholding(:'o_b');
select pg_temp.expect('TC-20 old year', 15000::numeric, (select wh_vat_amount from orders where id = :'o_a'));  -- 500.000 x 3%
select pg_temp.expect('TC-20 new year', 0::numeric, (select wh_vat_amount from orders where id = :'o_b'));

-- TC-21: a cancelled and a delivery_failed order with large computed revenue don't count:
-- 500.000 stays under the threshold -> 0.
select pg_temp.t_seller('g1 cancelled') as s5 \gset
select pg_temp.t_order(:'s5', 5000000, p_status => 'cancelled', p_paid_at => '2026-03-01 10:00+07') as o_c \gset
select pg_temp.t_order(:'s5', 5000000, p_status => 'delivery_failed', p_paid_at => '2026-03-01 11:00+07') as o_f \gset
select compute_order_withholding(:'o_c');
select compute_order_withholding(:'o_f');
select pg_temp.t_order(:'s5', 500000, p_paid_at => '2026-03-02 10:00+07') as o_d \gset
select compute_order_withholding(:'o_d');
select pg_temp.expect('TC-21 vat', 0::numeric, (select wh_vat_amount from orders where id = :'o_d'));

rollback;
