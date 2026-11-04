begin;
-- G5 daily portions (20261027010000_daily_portions.sql): reserve_order_portions holds the order's limited
-- dishes for its sale day (delivery_appointment, else paid_at, Vietnam date), all or nothing, once per order;
-- release_order_portions (trigger: pending / confirmed -> cancelled) hands them back; portions_left reads them.
\ir _fixtures.sql

select pg_temp.t_seller('g5') as s \gset
insert into food_items (seller_id, name, price, daily_portions) values (:'s', 'TEST sql five', 10000, 5) returning id as f5 \gset
insert into food_items (seller_id, name, price, daily_portions) values (:'s', 'TEST sql one', 10000, 1) returning id as f1 \gset
insert into food_items (seller_id, name, price, daily_portions) values (:'s', 'TEST sql edge', 10000, 5) returning id as fe \gset

-- TC-8 / TC-36: 5 a day on D = 10/11/2026. A takes 3, B (3) is refused, C (3) on D+1 is fine.
select pg_temp.t_order(:'s', 30000, p_status => 'pending', p_appointment => '2026-11-10 12:00+07') as a \gset
select pg_temp.t_order(:'s', 30000, p_status => 'pending', p_appointment => '2026-11-10 18:00+07') as b \gset
select pg_temp.t_order(:'s', 30000, p_status => 'pending', p_appointment => '2026-11-11 12:00+07') as c \gset
insert into order_items (order_id, food_item_id, quantity) values (:'a', :'f5', 3), (:'b', :'f5', 3), (:'c', :'f5', 3);
select pg_temp.expect('TC-36 A', true, reserve_order_portions(:'a'));
select pg_temp.expect('TC-36 left after A', 2, (select remaining from portions_left(array[:'f5']::uuid[], '2026-11-10')));
select pg_temp.expect('TC-36 B refused', false, reserve_order_portions(:'b'));
select pg_temp.expect('TC-36 B holds nothing', 0::bigint, (select count(*) from order_portion_holds where order_id = :'b'));
select pg_temp.expect('TC-36 C other day', true, reserve_order_portions(:'c'));
-- A again (IPN retry): true, nothing more held
select pg_temp.expect('TC-36 A again', true, reserve_order_portions(:'a'));
select pg_temp.expect('TC-36 A held once', 3::bigint, (select sum(qty) from order_portion_holds where order_id = :'a'));

-- TC-37: no appointment: the paid_at Vietnam day. 23:59:59 and 00:00:00 are two days, so 5 + 5 both fit.
select pg_temp.t_order(:'s', 50000, p_status => 'pending', p_paid_at => '2026-11-20 23:59:59+07') as late \gset
select pg_temp.t_order(:'s', 50000, p_status => 'pending', p_paid_at => '2026-11-21 00:00:00+07') as early \gset
insert into order_items (order_id, food_item_id, quantity) values (:'late', :'fe', 5), (:'early', :'fe', 5);
select pg_temp.expect('TC-37 late', true, reserve_order_portions(:'late'));
select pg_temp.expect('TC-37 early', true, reserve_order_portions(:'early'));
select pg_temp.expect('TC-37 late day', '2026-11-20'::date, (select sale_date from order_portion_holds where order_id = :'late'));
select pg_temp.expect('TC-37 early day', '2026-11-21'::date, (select sale_date from order_portion_holds where order_id = :'early'));

-- TC-38: two limited dishes, the second has 1 left and the order wants 2: refused, the first not held either.
select pg_temp.t_order(:'s', 30000, p_status => 'pending', p_appointment => '2026-11-12 12:00+07') as two \gset
insert into order_items (order_id, food_item_id, quantity) values (:'two', :'f5', 1), (:'two', :'f1', 2);
select pg_temp.expect('TC-38 refused', false, reserve_order_portions(:'two'));
select pg_temp.expect('TC-38 nothing held', 0::bigint, (select count(*) from order_portion_holds where order_id = :'two'));
select pg_temp.expect('TC-38 first dish untouched', 5, (select remaining from portions_left(array[:'f5']::uuid[], '2026-11-12')));

-- TC-8 / TC-38: cancelling A hands its 3 back; a second cancel update hands back nothing more.
update orders set status = 'cancelled' where id = :'a';
select pg_temp.expect('TC-8 released', 5, (select remaining from portions_left(array[:'f5']::uuid[], '2026-11-10')));
update orders set status = 'cancelled' where id = :'a';
select pg_temp.expect('TC-38 released once', 5, (select remaining from portions_left(array[:'f5']::uuid[], '2026-11-10')));
-- B now fits
select pg_temp.expect('TC-8 B after release', true, reserve_order_portions(:'b'));
select pg_temp.expect('TC-8 left', 2, (select remaining from portions_left(array[:'f5']::uuid[], '2026-11-10')));

rollback;
