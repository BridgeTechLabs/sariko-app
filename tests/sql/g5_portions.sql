begin;
-- G5 dish stock (20261113180000_dish_stock.sql, seller-menu đợt 2 S1, was daily portions): reserve_order_stock takes
-- a paid order's portions from food_items.stock, all or nothing, once per order, and lists the dishes that just went
-- below their minimum per order (one push each, cooldown); release_order_portions (trigger: pending / confirmed ->
-- cancelled) gives them back once; the old backend's reserve_order_portions / portions_left read the stock.
-- Two sessions racing (TC2-2, TC2-38) are tester / DEV cases: one transaction here.
\ir _fixtures.sql

select pg_temp.t_seller('g5') as s \gset
select (select count(*) from history_menu) as hist0 \gset

-- TC2-10 / TC2-40: the migration's conversion, run again on dishes made here (it only fills stock still null).
-- 5 a day, held today 2 + tomorrow 1 + yesterday 4 -> 2 left, yesterday's hold gone; 150000 a day -> the 100000 bound.
insert into food_items (seller_id, name, price, daily_portions) values (:'s', 'TEST sql conv', 10000, 5) returning id as fc \gset
insert into food_items (seller_id, name, price, daily_portions) values (:'s', 'TEST sql big', 10000, 150000) returning id as fb \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as o_today \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as o_tomorrow \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as o_yesterday \gset
insert into order_portion_holds (order_id, food_item_id, sale_date, qty) values
  (:'o_today', :'fc', (now() at time zone 'Asia/Ho_Chi_Minh')::date, 2),
  (:'o_tomorrow', :'fc', (now() at time zone 'Asia/Ho_Chi_Minh')::date + 1, 1),
  (:'o_yesterday', :'fc', (now() at time zone 'Asia/Ho_Chi_Minh')::date - 1, 4);
\ir ../../backend/supabase/migrations/20261113180000_dish_stock.sql
select pg_temp.expect('TC2-10 stock', 2, (select stock from food_items where id = :'fc'));
select pg_temp.expect('TC2-10 past hold gone', 0::bigint, (select count(*) from order_portion_holds where order_id = :'o_yesterday'));
select pg_temp.expect('TC2-10 later holds kept', 2::bigint,
                      (select count(*) from order_portion_holds where order_id in (:'o_today', :'o_tomorrow')));
select pg_temp.expect('TC2-40 bound', 100000, (select stock from food_items where id = :'fb'));
select pg_temp.expect('TC2-12 conversion not in history', :hist0::bigint, (select count(*) from history_menu));

-- TC2-1 / TC2-3: stock 2, two orders of 1. The second one takes the last portion and lists the dish; again: nothing.
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql two', 10000, 2) returning id as f2 \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as a \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as b \gset
insert into order_items (order_id, food_item_id, quantity) values (:'a', :'f2', 1), (:'b', :'f2', 1);
select pg_temp.expect('TC2-1 A', '[]'::jsonb, reserve_order_stock(:'a'));
select pg_temp.expect('TC2-1 B lists the dish', :'f2', reserve_order_stock(:'b') -> 0 ->> 'id');
select pg_temp.expect('TC2-1 stock 0', 0, (select stock from food_items where id = :'f2'));
select pg_temp.expect('TC2-1 holds', 2::bigint, (select count(*) from order_portion_holds where food_item_id = :'f2'));
select pg_temp.expect('TC2-3 B again', '[]'::jsonb, reserve_order_stock(:'b'));
select pg_temp.expect('TC2-3 no second take', 0, (select stock from food_items where id = :'f2'));
select pg_temp.expect('TC2-12 orders not in history', :hist0::bigint, (select count(*) from history_menu));

-- TC2-4: A has 5, B has 1, the order wants 1 + 2: null, nothing taken.
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql A', 10000, 5) returning id as fa \gset
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql B', 10000, 1) returning id as fbb \gset
select pg_temp.t_order(:'s', 30000, p_status => 'pending') as short \gset
insert into order_items (order_id, food_item_id, quantity) values (:'short', :'fa', 1), (:'short', :'fbb', 2);
select pg_temp.expect('TC2-4 null', null::jsonb, reserve_order_stock(:'short'));
select pg_temp.expect('TC2-4 A kept', 5, (select stock from food_items where id = :'fa'));
select pg_temp.expect('TC2-4 B kept', 1, (select stock from food_items where id = :'fbb'));
select pg_temp.expect('TC2-4 no holds', 0::bigint, (select count(*) from order_portion_holds where order_id = :'short'));

-- TC2-36 / TC2-11: no limited dish -> [] (not null); 10 minus 1 -> [] and 9; the old wrapper says true for both.
insert into food_items (seller_id, name, price) values (:'s', 'TEST sql free', 10000) returning id as ff \gset
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql ten', 10000, 10) returning id as f10 \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as nolimit \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as one \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as wrap \gset
insert into order_items (order_id, food_item_id, quantity) values (:'nolimit', :'ff', 3), (:'one', :'f10', 1), (:'wrap', :'f10', 1);
select pg_temp.expect('TC2-36 no limit', '[]'::jsonb, reserve_order_stock(:'nolimit'));
select pg_temp.expect('TC2-36 one of ten', '[]'::jsonb, reserve_order_stock(:'one'));
select pg_temp.expect('TC2-36 nine', 9, (select stock from food_items where id = :'f10'));
select pg_temp.expect('TC2-11 wrapper', true, reserve_order_portions(:'wrap'));
select pg_temp.expect('TC2-11 wrapper took', 8, (select stock from food_items where id = :'f10'));
select pg_temp.expect('TC2-11 portions_left', 8, (select remaining from portions_left(array[:'f10', :'ff']::uuid[], current_date)));
select pg_temp.expect('TC2-11 portions_left no limit', 1::bigint, (select count(*) from portions_left(array[:'f10', :'ff']::uuid[], current_date)));

-- TC2-8: minimum 3, stock 4, an order of 2 -> 2 left, below 3: listed with its numbers.
insert into food_items (seller_id, name, price, stock, min_quantity) values (:'s', 'TEST sql min', 10000, 4, 3) returning id as fm \gset
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as m \gset
insert into order_items (order_id, food_item_id, quantity) values (:'m', :'fm', 2);
select reserve_order_stock(:'m') as m_list \gset
select pg_temp.expect('TC2-8 listed', jsonb_build_array(jsonb_build_object('id', :'fm', 'name', 'TEST sql min', 'stock', 2, 'min_quantity', 3)),
                      :'m_list'::jsonb);

-- TC2-9: already below (2 < 3) and pushed a moment ago (TC2-8), the seller enters 10, an order of 8 crosses once:
-- the seller PATCH writes stock and clears stock_alert_at in one update (apis/sellers.py, P1; pytest test_tc2_22).
update food_items set stock = 10, stock_alert_at = null where id = :'fm';   -- the PATCH's update, as the DAO sends it
select pg_temp.t_order(:'s', 80000, p_status => 'pending') as m8 \gset
insert into order_items (order_id, food_item_id, quantity) values (:'m8', :'fm', 8);
select pg_temp.expect('TC2-9 one push', 1, jsonb_array_length(reserve_order_stock(:'m8')));

-- TC2-33: sold out (stamped), a cancel gives 1 back, sold out again within the cooldown: not listed;
-- the stamp older than the cooldown: listed again.
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql cool', 10000, 1) returning id as fk \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as k1 \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as k2 \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as k3 \gset
insert into order_items (order_id, food_item_id, quantity) values (:'k1', :'fk', 1), (:'k2', :'fk', 1), (:'k3', :'fk', 1);
select pg_temp.expect('TC2-33 first', 1, jsonb_array_length(reserve_order_stock(:'k1', 30)));
update orders set status = 'cancelled' where id = :'k1';
select pg_temp.expect('TC2-33 given back', 1, (select stock from food_items where id = :'fk'));
select pg_temp.expect('TC2-33 within cooldown', '[]'::jsonb, reserve_order_stock(:'k2', 30));
select pg_temp.expect('TC2-33 still taken', 0, (select stock from food_items where id = :'fk'));
update food_items set stock = 1, stock_alert_at = now() - interval '31 minutes' where id = :'fk';
select pg_temp.expect('TC2-33 after cooldown', 1, jsonb_array_length(reserve_order_stock(:'k3', 30)));

-- TC2-5 / TC2-6 / TC2-7 / TC2-39: cancels.
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql back', 10000, 5) returning id as fr \gset
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as p \gset
select pg_temp.t_order(:'s', 20000, p_status => 'ready') as r \gset
select pg_temp.t_order(:'s', 20000, p_status => 'confirmed') as nl \gset
insert into order_items (order_id, food_item_id, quantity) values (:'p', :'fr', 2), (:'r', :'fr', 2), (:'nl', :'f10', 2);
select reserve_order_stock(:'p'), reserve_order_stock(:'r'), reserve_order_stock(:'nl');
select pg_temp.expect('TC2-5 taken', 1, (select stock from food_items where id = :'fr'));
update orders set status = 'cancelled' where id = :'p';
select pg_temp.expect('TC2-5 given back', 3, (select stock from food_items where id = :'fr'));
select pg_temp.expect('TC2-5 holds gone', 0::bigint, (select count(*) from order_portion_holds where order_id = :'p'));
update orders set status = 'cancelled' where id = :'p';
select pg_temp.expect('TC2-5 once', 3, (select stock from food_items where id = :'fr'));
update orders set status = 'cancelled' where id = :'r';
select pg_temp.expect('TC2-6 cooked: kept', 3, (select stock from food_items where id = :'fr'));
update food_items set stock = null where id = :'f10';
update orders set status = 'cancelled' where id = :'nl';
select pg_temp.expect('TC2-7 no limit stays', null::integer, (select stock from food_items where id = :'f10'));
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql edge', 10000, 99999) returning id as fe \gset
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as e \gset
insert into order_items (order_id, food_item_id, quantity) values (:'e', :'fe', 2);
select reserve_order_stock(:'e');
update food_items set stock = 100000 where id = :'fe';
update orders set status = 'cancelled' where id = :'e';
select pg_temp.expect('TC2-39 bound kept', 100000, (select stock from food_items where id = :'fe'));

-- TC2-13: the input bound.
select pg_temp.expect_error('TC2-13 negative', format('update food_items set stock = -1 where id = %L', :'fe'), '%food_items_stock_check%');
select pg_temp.expect_error('TC2-13 too big', format('update food_items set stock = 100001 where id = %L', :'fe'), '%food_items_stock_check%');

-- TC2-12 / TC2-46: stock alone (seller saving twice) leaves no history row; a rename does.
select (select count(*) from history_menu) as hist1 \gset
update food_items set stock = 5 where id = :'fe';
update food_items set stock = 5 where id = :'fe';
select pg_temp.expect('TC2-46 stock only', :hist1::bigint, (select count(*) from history_menu));
update food_items set name = 'TEST sql edge 2' where id = :'fe';
select pg_temp.expect('TC2-12 rename logged', :hist1::bigint + 1, (select count(*) from history_menu));

-- TC2-34: only the backend (service role) runs the stock functions.
select pg_temp.expect('TC2-34 ' || f || ' ' || r, r = 'service_role', has_function_privilege(r, f, 'execute'))
  from unnest(array['reserve_order_stock(uuid, integer)', 'reserve_order_portions(uuid)',
                    'portions_left(uuid[], date)', 'release_order_portions()']) f,
       unnest(array['anon', 'authenticated', 'service_role']) r;

-- The setting the backend reads for the cooldown (BM13)
select pg_temp.expect('stock_alert_cooldown_minutes', '30'::jsonb, (select value from admin_settings where key = 'stock_alert_cooldown_minutes'));

rollback;
