begin;
-- G11 deliveries (T180 A26 + A12, docs/dev/20261110-delivery-tech, migration 20261110191000): at most one LIVE trip row
-- per order (status not ended); ended rows are not limited; trip_fee keeps the trip's price.
\ir _fixtures.sql

select pg_temp.t_seller('g11') as s \gset
select pg_temp.t_order(:'s', 100000, p_status => 'ready') as o \gset

-- TC-A26a: a live row, then a second live row for the same order -> refused by the unique index
insert into public.deliveries (order_id, provider, status, trip_fee) values (:'o', 'lalamove', 'ASSIGNING_DRIVER', 34800);
select pg_temp.expect_error('TC-A26a second live trip',
  format($q$insert into public.deliveries (order_id, provider, status) values (%L, 'lalamove', 'ON_GOING')$q$, :'o'),
  '%deliveries_one_live_trip_per_order%');
-- an ended row and a new live one: allowed (the old trip ended)
update public.deliveries set status = 'EXPIRED' where order_id = :'o';
insert into public.deliveries (order_id, provider, status) values (:'o', 'allingo', 'ASSIGNING_DRIVER');
select pg_temp.expect('TC-A26a ended + live', 2::bigint, (select count(*) from public.deliveries where order_id = :'o'));
-- a rebook rewrites its row: live -> live on the same row is fine
update public.deliveries set status = 'ON_GOING' where order_id = :'o' and status = 'ASSIGNING_DRIVER';
-- TC-A12a: the fee is kept as a whole number
select pg_temp.expect('TC-A12a trip fee', 34800::numeric,
  (select trip_fee from public.deliveries where order_id = :'o' and status = 'EXPIRED'));

rollback;
