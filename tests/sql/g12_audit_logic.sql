begin;
-- G12 T181 logic + T182 (docs/dev/20261110-audit-rest): unpaid_order_expire_minutes (A28), hidden reviews and their
-- scores (A33), the IPN's payment write (A35), the complaint payout hold with two open complaints (T182).
\ir _fixtures.sql

-- TC-A28b: the key exists and is a whole number > 0 (its value is the team's to change on DEV).
select pg_temp.expect('TC-A28b unpaid_order_expire_minutes', true,
  (select jsonb_typeof(value) = 'number' and (value #>> '{}')::numeric > 0 and (value #>> '{}')::numeric % 1 = 0
     from public.admin_settings where key = 'unpaid_order_expire_minutes'));

-- ── A33: hidden reviews leave the scores and the public reads ───────────────────────────────────────────────
select pg_temp.t_seller('g11') as s \gset
insert into food_items (seller_id, name, price) values (:'s', 'TEST sql g11 dish', 10000) returning id as f \gset
select pg_temp.t_order(:'s', 10000) as o1 \gset
select pg_temp.t_order(:'s', 10000) as o2 \gset
insert into public.review_stores (order_id, seller_id, user_id, rating, comment)
  select :'o1', :'s', user_id, 5, 'TEST sql' from public.orders where id = :'o1' returning id as r1 \gset
insert into public.review_stores (order_id, seller_id, user_id, rating, comment)
  select :'o2', :'s', user_id, 1, 'TEST sql' from public.orders where id = :'o2' returning id as r2 \gset
insert into public.review_items (order_id, seller_id, user_id, food_item_id, name_snapshot, rating)
  select :'o1', :'s', user_id, :'f', 'TEST sql g11 dish', 4 from public.orders where id = :'o1';
create function pg_temp.store_score(p uuid) returns text language sql as $$
  select coalesce(rating_avg::text, 'null') || '/' || coalesce(rating_count, 0) from public.seller_profiles where id = p $$;
create function pg_temp.dish_score(p uuid) returns text language sql as $$
  select coalesce(rating_avg::text, 'null') || '/' || coalesce(rating_count, 0) from public.food_items where id = p $$;

select pg_temp.expect('TC-A33a both shown', '3.0/2', pg_temp.store_score(:'s'));
update public.review_stores set is_hidden = true where id = :'r2';            -- the trigger runs on an is_hidden-only update (TC-A33d)
select pg_temp.expect('TC-A33a one hidden', '5.0/1', pg_temp.store_score(:'s'));
update public.review_stores set is_hidden = true where id = :'r1';
select pg_temp.expect('TC-A33d all hidden: no score, no division by 0', 'null/0', pg_temp.store_score(:'s'));
update public.review_stores set is_hidden = false where id in (:'r1', :'r2');
select pg_temp.expect('TC-A33a shown again', '3.0/2', pg_temp.store_score(:'s'));
select pg_temp.expect('TC-A33a dish', '4.0/1', pg_temp.dish_score(:'f'));

-- an order cancelled after its review (admin cancel + refund of a done order): its reviews hide themselves
update public.orders set status = 'cancelled' where id = :'o1';
select pg_temp.expect('TC-A33 auto-hide store review', true, (select is_hidden from public.review_stores where id = :'r1'));
select pg_temp.expect('TC-A33 auto-hide dish review', 'null/0', pg_temp.dish_score(:'f'));
select pg_temp.expect('TC-A33 score after the cancel', '1.0/1', pg_temp.store_score(:'s'));

-- the public (anon / signed-in buyers) never reads a hidden row
set local role anon;
select count(*) as anon_seen from public.review_stores where id in (:'r1', :'r2') \gset
reset role;
select pg_temp.expect('TC-A33e anon reads only shown rows', 1::bigint, :anon_seen::bigint);

-- ── A35: the IPN touches only this payment's charge row ─────────────────────────────────────────────────────
select pg_temp.t_order(:'s', 50000, p_status => 'pending', p_paid_at => null) as p \gset
insert into public.payments (order_id, method, amount, status, transaction_ref, type)
values (:'p', 'vnpay', 50000, 'failed', 'TEST-TXN-A', 'charge'),
       (:'p', 'vnpay', 50000, 'failed', 'TEST-TXN-B', 'charge'),
       (:'p', 'vnpay', 50000, 'succeeded', 'TEST-TXN-R', 'refund');
select update_order_payment_status(:'p', 'paid', 'TEST-TXN-C');
insert into public.payments (order_id, method, amount, status, transaction_ref, type)
values (:'p', 'vnpay', 50000, 'succeeded', 'TEST-TXN-C', 'charge');          -- the IPN writes it after the call
select pg_temp.expect('TC-A35c earlier attempts keep their result', 'TEST-TXN-A failed,TEST-TXN-B failed',
  (select string_agg(transaction_ref || ' ' || status, ',' order by transaction_ref) from public.payments
    where order_id = :'p' and type = 'charge' and transaction_ref <> 'TEST-TXN-C'));
select pg_temp.expect('TC-A35c refund row untouched', 'succeeded TEST-TXN-R',
  (select status || ' ' || transaction_ref from public.payments where order_id = :'p' and type = 'refund'));
select update_order_payment_status(:'p', 'paid', 'TEST-TXN-C');                -- the IPN sent again
select pg_temp.expect('TC-A35c this charge succeeded', 'succeeded',
  (select status from public.payments where order_id = :'p' and transaction_ref = 'TEST-TXN-C'));
select pg_temp.expect('TC-A35c order', 'paid TEST-TXN-C', (select payment_status || ' ' || transaction_ref from public.orders where id = :'p'));
select pg_temp.expect('TC-A35c definer', true, (select prosecdef from pg_proc where oid = 'public.update_order_payment_status(uuid, text, text)'::regprocedure));
select pg_temp.expect('TC-A35c anon', false, has_function_privilege('anon', 'public.update_order_payment_status(uuid, text, text)', 'execute'));

-- ── T182: two open complaints on one order ──────────────────────────────────────────────────────────────────
select pg_temp.t_order(:'s', 80000) as c \gset
update public.orders set payout_status = 'pending', payout_hold = false where id = :'c';
select (public.create_complaint(:'c', (select user_id from public.orders where id = :'c'), 'buyer', 'app', 'late', 'TEST sql'))->>'id' as kb \gset
select (public.create_complaint(:'c', (select user_id from public.seller_profiles where id = :'s'), 'seller', 'app', 'other', 'TEST sql'))->>'id' as ks \gset
create function pg_temp.hold(p uuid) returns text language sql as $$
  select payout_hold::text || ' ' || coalesce(payout_hold_note, '-') from public.orders where id = p $$;
select pg_temp.expect('TC-T182a the buyer complaint holds', 'true complaint ' || (select code from public.complaints where id = :'kb'), pg_temp.hold(:'c'));
select public.set_complaint_status(:'kb', 'resolved', 'TEST sql done');
select pg_temp.expect('TC-T182a still held, by the other complaint', 'true complaint ' || (select code from public.complaints where id = :'ks'), pg_temp.hold(:'c'));
select public.set_complaint_status(:'ks', 'resolved', 'TEST sql done');
select pg_temp.expect('TC-T182a released by the last one', 'false -', pg_temp.hold(:'c'));

-- the other order: the seller's complaint resolved first changes nothing; a hold an admin set by hand is never released
select pg_temp.t_order(:'s', 80000) as d \gset
update public.orders set payout_status = 'pending', payout_hold = false where id = :'d';
select (public.create_complaint(:'d', (select user_id from public.orders where id = :'d'), 'buyer', 'app', 'late', 'TEST sql'))->>'id' as db \gset
select (public.create_complaint(:'d', (select user_id from public.seller_profiles where id = :'s'), 'seller', 'app', 'other', 'TEST sql'))->>'id' as ds \gset
select public.set_complaint_status(:'ds', 'resolved', 'TEST sql done');
select pg_temp.expect('TC-T182b seller first: still held', 'true complaint ' || (select code from public.complaints where id = :'db'), pg_temp.hold(:'d'));
update public.orders set payout_hold_note = 'TEST sql manual hold' where id = :'d';
select public.set_complaint_status(:'db', 'resolved', 'TEST sql done');
select pg_temp.expect('TC-T182b a manual hold stays', 'true TEST sql manual hold', pg_temp.hold(:'d'));

rollback;
