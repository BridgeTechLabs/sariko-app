begin;
-- G-seller-order (20261116120000_seller_order_pin.sql, flow 20261116-seller-order): is_pinned + display_order default,
-- admin_apply_seller_order (all or none, unknown / repeated id = error, only 2 columns written), the apply / undo
-- wrappers (one log row, undo once, a deleted store skipped, no log when nothing changed), grants (service role only).
\ir _fixtures.sql

-- TC-10: the migration twice fails nothing; a store that exists is not pinned
select pg_temp.t_seller('so a') as a \gset
select pg_temp.t_seller('so b') as b \gset
select pg_temp.t_seller('so c') as c \gset
\ir ../../backend/supabase/migrations/20261116120000_seller_order_pin.sql
select pg_temp.expect('TC-10 not pinned', false, (select is_pinned from public.seller_profiles where id = :'a'));
select pg_temp.expect('TC-10 default order', 1000000, (select column_default::int from information_schema.columns
  where table_schema = 'public' and table_name = 'seller_profiles' and column_name = 'display_order'));

-- a store made after the migration gets the default and is not pinned
select pg_temp.t_seller('so new') as n \gset
select pg_temp.expect('TC-12 new store goes last', 1000000, (select display_order::int from public.seller_profiles where id = :'n'));

-- the actions already in the log (DEV keeps real ones) are not ours: count from here
select coalesce(max(id), 0) as log0 from public.history_admin_actions \gset

-- TC-6: one unknown id in the list = error, nobody changes
update public.seller_profiles set display_order = 5, is_pinned = false where id in (:'a', :'b', :'c');
select pg_temp.expect_error('TC-6 unknown id', format($$select public.admin_apply_seller_order('[{"id":"%s","display_order":10,"is_pinned":true},
  {"id":"00000000-0000-4000-8000-000000000000","display_order":20,"is_pinned":false}]'::jsonb)$$, :'a'), '%unknown seller id%');
select pg_temp.expect('TC-6 nobody changed', 0::bigint,
  (select count(*) from public.seller_profiles where id in (:'a', :'b', :'c') and (display_order <> 5 or is_pinned)));

-- TC-30: the same id twice = error, nobody changes
select pg_temp.expect_error('TC-30 repeated id', format($$select public.admin_apply_seller_order('[{"id":"%1$s","display_order":10,"is_pinned":true},
  {"id":"%1$s","display_order":20,"is_pinned":false}]'::jsonb)$$, :'a'), '%missing or repeated%');
select pg_temp.expect('TC-30 nobody changed', 0::bigint,
  (select count(*) from public.seller_profiles where id in (:'a', :'b', :'c') and (display_order <> 5 or is_pinned)));
select pg_temp.expect_error('not an array', $$select public.admin_apply_seller_order('{}'::jsonb)$$, '%json array%');

-- TC-31: only display_order + is_pinned change; opened_at / is_open stay
select to_jsonb(s) - 'display_order' - 'is_pinned' as a_before from public.seller_profiles s where id = :'a' \gset
select public.admin_apply_seller_order(format('[{"id":"%s","display_order":10,"is_pinned":true}]', :'a')::jsonb) as ch \gset
select pg_temp.expect('TC-31 changed count', 1, :ch::int);
select pg_temp.expect('TC-31 other columns same', :'a_before'::jsonb,
  (select to_jsonb(s) - 'display_order' - 'is_pinned' from public.seller_profiles s where id = :'a'));
select pg_temp.expect('TC-31 values', '10 true', (select display_order || ' ' || is_pinned from public.seller_profiles where id = :'a'));
select public.admin_apply_seller_order(format('[{"id":"%s","display_order":10,"is_pinned":true}]', :'a')::jsonb) as ch \gset
select pg_temp.expect('same values = 0 changed', 0, :ch::int);

-- TC-5 / TC-33: apply logs before + after (with group) and the actor; a repeat changes nothing and logs nothing
update public.seller_profiles set display_order = 5, is_pinned = false where id in (:'a', :'b', :'c');
select format('[{"id":"%s","display_order":10,"is_pinned":true,"group":"active"},{"id":"%s","display_order":20,"is_pinned":false,"group":"active"},
  {"id":"%s","display_order":10,"is_pinned":false,"group":"coming_soon"}]', :'a', :'b', :'c') as rows \gset
select public.admin_seller_order_apply(:'rows'::jsonb, 'ops@sariko.store') ->> 'changed' as ch \gset
select pg_temp.expect('TC-5 changed', '3', :'ch');
select pg_temp.expect('TC-5 orders', '10 20 10', (select string_agg(display_order::text, ' ' order by store_name) from public.seller_profiles where id in (:'a', :'b', :'c')));
select pg_temp.expect('TC-33 one apply row', 1::bigint, (select count(*) from public.history_admin_actions where id > :log0 and action = 'seller_order_apply'));
select pg_temp.expect('TC-33 actor', 'ops@sariko.store', (select actor from public.history_admin_actions where id > :log0 and action = 'seller_order_apply'));
select pg_temp.expect('TC-33 before has all 3, old numbers', 3, (select count(*)::int from public.history_admin_actions h, jsonb_array_elements(h.params -> 'before') b
  where h.id > :log0 and h.action = 'seller_order_apply' and (b ->> 'display_order') = '5' and b ->> 'is_pinned' = 'false'));
select pg_temp.expect('TC-33 after has the group', 2, (select count(*)::int from public.history_admin_actions h, jsonb_array_elements(h.params -> 'after') b
  where h.id > :log0 and h.action = 'seller_order_apply' and b ->> 'group' = 'active'));
select public.admin_seller_order_apply(:'rows'::jsonb, 'ops@sariko.store') ->> 'changed' as ch \gset
select pg_temp.expect('TC-20 repeat changes nothing', '0', :'ch');
select pg_temp.expect('TC-20 and logs nothing', 1::bigint, (select count(*) from public.history_admin_actions where id > :log0 and action = 'seller_order_apply'));

-- TC-8 / TC-23 / TC-24: undo goes back to "before"; a hand edit is overwritten; a deleted store is skipped; a hidden one is restored
update public.seller_profiles set display_order = 99 where id = :'a';
update public.seller_profiles set is_listed = false where id = :'b';
delete from public.seller_profiles where id = :'c';
select public.admin_seller_order_undo('ops@sariko.store') as u \gset
select pg_temp.expect('TC-8 status', 'ok', (:'u'::jsonb) ->> 'status');
select pg_temp.expect('TC-23 restored / skipped', '2 1', (:'u'::jsonb ->> 'restored') || ' ' || (:'u'::jsonb ->> 'skipped'));
select pg_temp.expect('TC-8 / 24 back to before', '5 false', (select display_order || ' ' || is_pinned from public.seller_profiles where id = :'a'));
select pg_temp.expect('TC-23 hidden one restored', '5 false', (select display_order || ' ' || is_pinned from public.seller_profiles where id = :'b'));
select pg_temp.expect('TC-8 undo row', 1::bigint, (select count(*) from public.history_admin_actions where id > :log0 and action = 'seller_order_undo'));
-- TC-8: the second undo has nothing to do; so does an undo with the latest row being an undo
select pg_temp.expect('TC-8 second undo', 'nothing_to_undo', public.admin_seller_order_undo('ops@sariko.store') ->> 'status');
select pg_temp.expect('TC-8 still one undo row', 1::bigint, (select count(*) from public.history_admin_actions where id > :log0 and action = 'seller_order_undo'));
-- apply twice, undo: back to the state before the second apply (TC-8)
select public.admin_seller_order_apply(format('[{"id":"%s","display_order":10,"is_pinned":true}]', :'a')::jsonb, 'x') as r1 \gset
select public.admin_seller_order_apply(format('[{"id":"%s","display_order":30,"is_pinned":false}]', :'a')::jsonb, 'x') as r2 \gset
select public.admin_seller_order_undo('x') as r3 \gset
select pg_temp.expect('TC-8 before the second apply', '10 true', (select display_order || ' ' || is_pinned from public.seller_profiles where id = :'a'));

-- TC-29: the client roles cannot call any of the three functions
-- (pg_temp helpers are not callable under these roles: plain DO blocks)
set local role authenticated;
do $$ begin perform public.admin_apply_seller_order('[]'::jsonb); raise exception 'TC-29: authenticated ran the core';
  exception when insufficient_privilege then null; end $$;
do $$ begin perform public.admin_seller_order_apply('[]'::jsonb, 'x'); raise exception 'TC-29: authenticated ran apply';
  exception when insufficient_privilege then null; end $$;
do $$ begin perform public.admin_seller_order_undo('x'); raise exception 'TC-29: authenticated ran undo';
  exception when insufficient_privilege then null; end $$;
set local role anon;
do $$ begin perform public.admin_seller_order_apply('[]'::jsonb, 'x'); raise exception 'TC-29: anon ran apply';
  exception when insufficient_privilege then null; end $$;
do $$ begin perform public.admin_seller_order_undo('x'); raise exception 'TC-29: anon ran undo';
  exception when insufficient_privilege then null; end $$;
reset role;

-- no TEST row is left: the test's own transaction rolls back
rollback;
