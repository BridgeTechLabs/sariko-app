begin;
-- G5 dish stock (20261113180000_dish_stock.sql + 20261113210000_dish_stock_cleanup.sql, seller-menu đợt 2 / 4A):
-- reserve_order_stock takes a paid pending order's portions from food_items.stock, all or nothing, once per order, and
-- lists the dishes that just went below their minimum per order (one push each, cooldown); an order no longer pending
-- takes nothing (T205); release_order_portions (trigger: pending / confirmed -> cancelled) gives them back once.
-- Two sessions racing (TC2-2, TC2-38, TC4-7) are tester / DEV cases: one transaction here.
\ir _fixtures.sql

select pg_temp.t_seller('g5') as s \gset
select (select count(*) from history_menu) as hist0 \gset

-- TC4-1: the old columns, index and wrappers are gone (T204).
select pg_temp.expect('TC4-1 columns', 0::bigint, (select count(*) from information_schema.columns where table_schema = 'public'
          and ((table_name = 'food_items' and column_name = 'daily_portions') or (table_name = 'order_portion_holds' and column_name = 'sale_date'))));
select pg_temp.expect('TC4-1 wrappers', 0::bigint, (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
          where n.nspname = 'public' and p.proname in ('reserve_order_portions', 'portions_left')));
select pg_temp.expect('TC4-1 index', 0::bigint, (select count(*) from pg_indexes where indexname = 'idx_order_portion_holds_food_date'));
select pg_temp.expect('TC4-1 no sale_date in functions', 0::bigint, (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
          where n.nspname = 'public' and p.prosrc ~ 'sale_date|daily_portions'));

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

-- TC2-36 / TC4-2: no limited dish -> [] (not null); 10 minus 1 -> [] and 9, one hold row; 1 more -> 8.
insert into food_items (seller_id, name, price) values (:'s', 'TEST sql free', 10000) returning id as ff \gset
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql ten', 10000, 10) returning id as f10 \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as nolimit \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as one \gset
select pg_temp.t_order(:'s', 10000, p_status => 'pending') as wrap \gset
insert into order_items (order_id, food_item_id, quantity) values (:'nolimit', :'ff', 3), (:'one', :'f10', 1), (:'wrap', :'f10', 1);
select pg_temp.expect('TC2-36 no limit', '[]'::jsonb, reserve_order_stock(:'nolimit'));
select pg_temp.expect('TC2-36 one of ten', '[]'::jsonb, reserve_order_stock(:'one'));
select pg_temp.expect('TC2-36 nine', 9, (select stock from food_items where id = :'f10'));
select pg_temp.expect('TC4-2 one hold', 1::bigint, (select count(*) from order_portion_holds where order_id = :'one'));
select pg_temp.expect('TC4-2 another order', '[]'::jsonb, reserve_order_stock(:'wrap'));
select pg_temp.expect('TC4-2 took', 8, (select stock from food_items where id = :'f10'));

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
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as r \gset
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as nl \gset
insert into order_items (order_id, food_item_id, quantity) values (:'p', :'fr', 2), (:'r', :'fr', 2), (:'nl', :'f10', 2);
select reserve_order_stock(:'p'), reserve_order_stock(:'r'), reserve_order_stock(:'nl');   -- paid while pending
update orders set status = 'ready' where id = :'r';
update orders set status = 'confirmed' where id = :'nl';
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

-- TC4-3 / T205: an order cancelled before the payment lands takes nothing, holds nothing.
insert into food_items (seller_id, name, price, stock) values (:'s', 'TEST sql late', 10000, 5) returning id as fl \gset
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as late \gset
insert into order_items (order_id, food_item_id, quantity) values (:'late', :'fl', 2);
update orders set status = 'cancelled' where id = :'late';
select pg_temp.expect('TC4-3 cancelled', '[]'::jsonb, reserve_order_stock(:'late'));
select pg_temp.expect('TC4-3 stock kept', 5, (select stock from food_items where id = :'fl'));
select pg_temp.expect('TC4-3 no holds', 0::bigint, (select count(*) from order_portion_holds where order_id = :'late'));
-- TC4-4 / TC4-5: pending, taken once (again: nothing more), then cancelled: back to 5, no holds.
select pg_temp.t_order(:'s', 20000, p_status => 'pending') as once \gset
insert into order_items (order_id, food_item_id, quantity) values (:'once', :'fl', 2);
select pg_temp.expect('TC4-4 first', '[]'::jsonb, reserve_order_stock(:'once'));
select pg_temp.expect('TC4-4 again', '[]'::jsonb, reserve_order_stock(:'once'));
select pg_temp.expect('TC4-4 taken once', 3, (select stock from food_items where id = :'fl'));
update orders set status = 'cancelled' where id = :'once';
select pg_temp.expect('TC4-5 back', 5, (select stock from food_items where id = :'fl'));
select pg_temp.expect('TC4-5 no holds', 0::bigint, (select count(*) from order_portion_holds where order_id = :'once'));

-- TC4-14: an order id that does not exist: [] and nothing taken. TC4-15: confirmed without holds (paid before the
-- stock): [], nothing taken a second time.
select pg_temp.expect('TC4-14 unknown order', '[]'::jsonb, reserve_order_stock(gen_random_uuid()));
select pg_temp.t_order(:'s', 20000, p_status => 'confirmed') as conf \gset
insert into order_items (order_id, food_item_id, quantity) values (:'conf', :'fl', 2);
select pg_temp.expect('TC4-15 confirmed', '[]'::jsonb, reserve_order_stock(:'conf'));
select pg_temp.expect('TC4-15 stock kept', 5, (select stock from food_items where id = :'fl'));

-- TC4-27 / TC4-29 (T208): marking paid answers "the order still waits": a cancelled order is left as it is (false);
-- a pending one is marked, and again (an IPN retry / the reconcile job) still true, never refunded for it.
select pg_temp.t_order(:'s', 20000, p_status => 'cancelled', p_paid_at => null) as gone \gset
select pg_temp.expect('TC4-27 cancelled', false, update_order_payment_status(:'gone', 'paid', 'TXN-gone'));
select pg_temp.expect('TC4-27 unchanged', 'pending', (select payment_status from orders where id = :'gone'));
select pg_temp.expect('TC4-27 no paid_at', null::timestamptz, (select paid_at from orders where id = :'gone'));
select pg_temp.t_order(:'s', 20000, p_status => 'pending', p_paid_at => null) as wait \gset
select pg_temp.expect('TC4-29 first', true, update_order_payment_status(:'wait', 'paid', 'TXN-wait'));
select pg_temp.expect('TC4-29 again', true, update_order_payment_status(:'wait', 'paid', 'TXN-wait'));
select pg_temp.expect('TC4-29 paid', 'paid', (select payment_status from orders where id = :'wait'));

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
  from unnest(array['reserve_order_stock(uuid, integer)', 'release_order_portions()']) f,
       unnest(array['anon', 'authenticated', 'service_role']) r;

-- TC4-16 / TC4-31: every overload of update_order_payment_status (drop + create brought PUBLIC back) and
-- reserve_order_stock: only the backend.
select pg_temp.expect('TC4-31 ' || p.oid::regprocedure::text || ' ' || r, r = 'service_role', has_function_privilege(r, p.oid, 'execute'))
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace,
       unnest(array['anon', 'authenticated', 'service_role']) r
 where n.nspname = 'public' and p.proname in ('update_order_payment_status', 'reserve_order_stock');

-- The setting the backend reads for the cooldown (BM13)
select pg_temp.expect('stock_alert_cooldown_minutes', '30'::jsonb, (select value from admin_settings where key = 'stock_alert_cooldown_minutes'));

rollback;
