begin;
-- G13 (T192 C, docs/dev/20261111-admin-settings-pages, migration 20261111150000): AllinGo company switches, three
-- descriptions without "Lalamove", deliveries.allingo_partner. Values are not checked: an admin may change them.
\ir _fixtures.sql

-- TC-12: the 3 switches exist as 0 / 1; no description of the three booking settings names Lalamove
select pg_temp.expect('TC-12 company switches', 3::bigint, (select count(*) from public.admin_settings
  where key in ('allingo_partner_grab', 'allingo_partner_gsm', 'allingo_partner_lalamove') and value in ('0'::jsonb, '1'::jsonb)));
select pg_temp.expect('TC-12 no Lalamove', 0::bigint, (select count(*) from public.admin_settings
  where key in ('driver_booking_attempts', 'seller_rebook_max', 'buyer_cancel_late_delivery_failed_minutes')
    and description ilike '%lalamove%'));

-- TC-27: the column is null on a new row; setting it writes no history_delivery row (log_delivery looks at status
-- and the driver only)
select pg_temp.t_seller('g13') as s \gset
select pg_temp.t_order(:'s', 100000, p_status => 'ready') as o \gset
insert into public.deliveries (order_id, provider, status) values (:'o', 'allingo', 'ASSIGNING_DRIVER');
select pg_temp.expect('TC-27 null on a new row', null::text, (select allingo_partner from public.deliveries where order_id = :'o'));
select count(*) as before_history from public.history_delivery where order_id = :'o' \gset
update public.deliveries set allingo_partner = 'grab' where order_id = :'o';
select pg_temp.expect('TC-27 no history row', :before_history::bigint,
  (select count(*) from public.history_delivery where order_id = :'o'));

-- TC-28: the migration again (db push repeated) fails nothing and keeps a switch an admin changed
update public.admin_settings set value = '1'::jsonb where key = 'allingo_partner_lalamove';
\ir ../../backend/supabase/migrations/20261111150000_delivery_partner_settings.sql
select pg_temp.expect('TC-28 admin value kept', '1'::jsonb,
  (select value from public.admin_settings where key = 'allingo_partner_lalamove'));

rollback;
