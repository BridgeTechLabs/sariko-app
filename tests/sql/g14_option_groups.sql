begin;
-- G14 option groups (20261113120000_option_groups.sql, seller-menu đợt 3): add_cart_item merges one choice into one
-- cart row and enforces the caps, the CHECK on extra_price, the composite FKs (no group of another store on a dish),
-- the grants (only the backend calls add_cart_item, the client roles see none of the 3 tables), history_menu.
\ir _fixtures.sql

select pg_temp.t_seller('g14 a') as sa \gset
select pg_temp.t_seller('g14 b') as sb \gset
insert into food_items (seller_id, name, price) values (:'sa', 'TEST sql combo', 109000) returning id as dish \gset
insert into food_items (seller_id, name, price) values (:'sb', 'TEST sql other', 50000) returning id as dish_b \gset
insert into food_item_variants (food_item_id, name, price) values (:'dish', 'L', 150000) returning id as lvl \gset
insert into menu_option_groups (seller_id, name, is_required, max_select) values (:'sa', 'Drinks', true, 1) returning id as g \gset
insert into menu_option_groups (seller_id, name) values (:'sb', 'B') returning id as gb \gset
insert into menu_options (group_id, name, extra_price) values (:'g', 'Coca', 5000) returning id as oa \gset
insert into menu_options (group_id, name, extra_price) values (:'g', 'Egg', 5000) returning id as ob \gset
insert into food_item_option_groups (food_item_id, group_id, seller_id) values (:'dish', :'g', :'sa');
select id as buyer from public.users where name = 'TEST sql g14 a' \gset
insert into carts (user_id, seller_id) values (:'buyer', :'sa') returning id as cart \gset

-- TC3-16: extra_price must be whole and >= 0
select pg_temp.expect_error('TC3-16 negative', format($$insert into menu_options (group_id, name, extra_price) values (%L, 'x', -1)$$, :'g'), '%menu_options_extra_price_check%');
select pg_temp.expect_error('TC3-16 fraction', format($$insert into menu_options (group_id, name, extra_price) values (%L, 'y', 0.5)$$, :'g'), '%menu_options_extra_price_check%');
-- TC3-44 (database side): one name once per group
select pg_temp.expect_error('TC3-44 name', format($$insert into menu_options (group_id, name) values (%L, 'Coca')$$, :'g'), '%menu_options_group_name_key%');
-- One save swapping two names (DAOMenuOptionGroups.save_group: one upsert on the primary key) passes: the unique
-- name is deferrable, checked at the end of the statement, not row by row
insert into menu_options (id, group_id, name, extra_price) values (:'oa', :'g', 'Egg', 5000), (:'ob', :'g', 'Coca', 5000)
  on conflict (id) do update set name = excluded.name;
select pg_temp.expect('swap names', 'Egg', (select name from menu_options where id = :'oa'));
select pg_temp.expect_error('swap still unique', format($$insert into menu_options (id, group_id, name) values (%L, %L, 'Coca') on conflict (id) do update set name = excluded.name$$, :'oa', :'g'), '%menu_options_group_name_key%');
insert into menu_options (id, group_id, name, extra_price) values (:'oa', :'g', 'Coca', 5000), (:'ob', :'g', 'Egg', 5000)
  on conflict (id) do update set name = excluded.name;
-- TC3-15: a group of store B on a dish of store A (either seller_id) is refused by the composite FKs
select pg_temp.expect_error('TC3-15 group of B', format($$insert into food_item_option_groups (food_item_id, group_id, seller_id) values (%L, %L, %L)$$, :'dish', :'gb', :'sa'), '%food_item_option_groups_group_fkey%');
select pg_temp.expect_error('TC3-15 dish of A', format($$insert into food_item_option_groups (food_item_id, group_id, seller_id) values (%L, %L, %L)$$, :'dish', :'gb', :'sb'), '%food_item_option_groups_food_fkey%');
select pg_temp.expect_error('options_snapshot array', format($$insert into order_items (order_id, quantity, options_snapshot) values (%L, 1, '{}')$$, pg_temp.t_order(:'sa', 1000)), '%order_items_options_snapshot_check%');

-- TC3-4, TC3-36, TC3-59: same dish (no level) + same choice, in any order or repeated = one row, quantities added
select add_cart_item(:'cart', :'dish', null, array[:'ob', :'oa']::uuid[], 1, 50, 20);
select add_cart_item(:'cart', :'dish', null, array[:'oa', :'ob']::uuid[], 2, 50, 20);
select add_cart_item(:'cart', :'dish', null, array[:'oa', :'oa', :'ob']::uuid[], 3, 50, 20);
select pg_temp.expect('TC3-36 one row', 1::bigint, (select count(*) from cart_items where cart_id = :'cart'));
select pg_temp.expect('TC3-36 quantity', 6, (select quantity from cart_items where cart_id = :'cart'));
select pg_temp.expect('TC3-36 sorted ids', (select array_agg(x order by x) from unnest(array[:'oa', :'ob']::uuid[]) x),
                      (select option_ids from cart_items where cart_id = :'cart'));
-- TC3-5: another choice, the level, no options: other rows; the no-level no-options row merges too (NULLS NOT DISTINCT)
select add_cart_item(:'cart', :'dish', null, array[:'oa']::uuid[], 1, 50, 20);
select add_cart_item(:'cart', :'dish', :'lvl', array[:'oa']::uuid[], 1, 50, 20);
select add_cart_item(:'cart', :'dish', null, null, 1, 50, 20);
select add_cart_item(:'cart', :'dish', null, '{}', 1, 50, 20);
select pg_temp.expect('TC3-5 rows', 4::bigint, (select count(*) from cart_items where cart_id = :'cart'));
select pg_temp.expect('TC3-59 plain row', 2, (select quantity from cart_items where cart_id = :'cart' and option_ids = '{}'));
-- TC3-52 / TC3-60 / TC3-61: the dish total over all its rows (6 + 1 + 1 + 2 = 10); 40 more fits, 41 does not
select pg_temp.expect_error('TC3-52 total', format($$select add_cart_item(%L, %L, null, '{}', 41, 50, 20)$$, :'cart', :'dish'), 'quantity_max');
select add_cart_item(:'cart', :'dish', null, '{}', 40, 50, 20);
select pg_temp.expect('TC3-66 at the cap', 50::bigint, (select sum(quantity) from cart_items where cart_id = :'cart'));
-- TC3-64: rows cap (4 rows now): a 5th row with cap 4 is refused, adding to an existing row is not
select pg_temp.expect_error('TC3-64 rows', format($$select add_cart_item(%L, %L, null, array[%L]::uuid[], 1, 99, 4)$$, :'cart', :'dish', :'ob'), 'cart_max_lines');
select add_cart_item(:'cart', :'dish', null, array[:'oa']::uuid[], 1, 99, 4);

-- TC3-60 (BM9): the client roles can't call it through /rest/v1/rpc, nor touch the new tables
select pg_temp.expect('TC3-60 anon', false, has_function_privilege('anon', 'public.add_cart_item(uuid, uuid, uuid, uuid[], integer, integer, integer)', 'execute'));
select pg_temp.expect('TC3-60 authenticated', false, has_function_privilege('authenticated', 'public.add_cart_item(uuid, uuid, uuid, uuid[], integer, integer, integer)', 'execute'));
select pg_temp.expect('TC3-60 service_role', true, has_function_privilege('service_role', 'public.add_cart_item(uuid, uuid, uuid, uuid[], integer, integer, integer)', 'execute'));
select pg_temp.expect('RLS tables ' || t, false, has_table_privilege(r, 'public.' || t, 'select'))
  from unnest(array['menu_option_groups', 'menu_options', 'food_item_option_groups']) t, unnest(array['anon', 'authenticated']) r;

-- TC3-48: every update / delete on the 3 tables keeps the old row
select count(*) as h0 from history_menu \gset
update menu_option_groups set name = 'Drinks 2' where id = :'g';
update menu_options set extra_price = 7000 where id = :'oa';
update food_item_option_groups set sort_order = 1 where food_item_id = :'dish';
select pg_temp.expect('TC3-48 history', :h0 + 3::bigint, (select count(*) from history_menu));
select pg_temp.expect('TC3-48 each table', 3::bigint, (select count(distinct table_name) from history_menu
   where (table_name, row_id) in (('menu_option_groups', :'g'::uuid), ('menu_options', :'oa'::uuid))
      or (table_name = 'food_item_option_groups' and old_row ->> 'food_item_id' = :'dish')));

-- TC3-49: the dish deleted (after its cart rows) takes its links with it, the group stays
delete from cart_items where cart_id = :'cart';
delete from food_items where id = :'dish';
select pg_temp.expect('TC3-49 links gone', 0::bigint, (select count(*) from food_item_option_groups where group_id = :'g'));
select pg_temp.expect('TC3-49 group kept', 1::bigint, (select count(*) from menu_option_groups where id = :'g'));
select pg_temp.expect('TC3-49 delete logged', 1::bigint, (select count(*) from history_menu
   where table_name = 'food_item_option_groups' and op = 'DELETE' and old_row ->> 'food_item_id' = :'dish'));

rollback;
