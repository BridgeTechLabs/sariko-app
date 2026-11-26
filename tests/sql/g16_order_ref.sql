begin;
-- G16 order ref (20261123103614_order_ref.sql, flow 20261123-studio-integration TC-3, TC-16): the migration runs twice,
-- the setting is 7, the CHECKs refuse a ref with a space / over 64 characters and an empty or upper-case source,
-- and take a valid one or none.
\ir _fixtures.sql

\ir ../../backend/supabase/migrations/20261123103614_order_ref.sql
\ir ../../backend/supabase/migrations/20261123103614_order_ref.sql
select pg_temp.expect('TC-3 one setting row', 1::bigint, (select count(*) from public.admin_settings where key = 'attribution_window_days'));
select pg_temp.expect('TC-3 setting 7', '7'::jsonb, (select value from public.admin_settings where key = 'attribution_window_days'));

select pg_temp.t_seller('g16') as s \gset
select pg_temp.t_order(:'s', 100000) as o \gset

select pg_temp.expect_error('TC-3 ref with a space', format($q$update public.orders set ref_code = 'a b' where id = %L$q$, :'o'),
  '%orders_ref_code_check%');
select pg_temp.expect_error('TC-3 ref of 65', format($q$update public.orders set ref_code = repeat('a', 65) where id = %L$q$, :'o'),
  '%orders_ref_code_check%');
select pg_temp.expect_error('TC-3 empty source', format($q$update public.orders set ref_source = '' where id = %L$q$, :'o'),
  '%orders_ref_source_check%');
select pg_temp.expect_error('TC-3 upper-case source', format($q$update public.orders set ref_source = 'Facebook' where id = %L$q$, :'o'),
  '%orders_ref_source_check%');

update public.orders set ref_code = repeat('a', 64), ref_source = 'fb' where id = :'o';
update public.orders set ref_code = 'Ab3_x-9', ref_source = null where id = :'o';
select pg_temp.expect('TC-3 valid ref kept', 'Ab3_x-9'::text, (select ref_code from public.orders where id = :'o'));

-- no TEST row is left: the test's own transaction rolls back
rollback;
