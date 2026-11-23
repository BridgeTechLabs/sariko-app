begin;
-- G15 promo banners (20261121180000_promo_banners.sql, flow 20261121-promo-banners TC-4, TC-18): the migration runs
-- twice, the table starts empty, the CHECKs refuse http links / images, long alt and an unknown placement (TC-25),
-- the client roles read nothing.
\ir _fixtures.sql

\ir ../../backend/supabase/migrations/20261121180000_promo_banners.sql
\ir ../../backend/supabase/migrations/20261121180000_promo_banners.sql
select pg_temp.expect('TC-4 one setting row', 1::bigint, (select count(*) from public.admin_settings where key = 'promo_banner_max'));
select pg_temp.expect('TC-4 setting 10', '10'::jsonb, (select value from public.admin_settings where key = 'promo_banner_max'));

select pg_temp.expect_error('TC-4 http link', $$insert into public.admin_promo_banners (image_url, link_url, position)
  values ('https://x/a.webp', 'http://x', 1)$$, '%admin_promo_banners_link_url_check%');
select pg_temp.expect_error('TC-4 http image', $$insert into public.admin_promo_banners (image_url, link_url, position)
  values ('http://x', 'https://x', 1)$$, '%admin_promo_banners_image_url_check%');
select pg_temp.expect_error('TC-4 alt 121', $$insert into public.admin_promo_banners (image_url, link_url, alt, position)
  values ('https://x/a.webp', 'https://x', repeat('a', 121), 1)$$, '%admin_promo_banners_alt_check%');
select pg_temp.expect_error('TC-25 placement x', $$insert into public.admin_promo_banners (image_url, link_url, position, placement)
  values ('https://x/a.webp', 'https://x', 1, 'x')$$, '%admin_promo_banners_placement_check%');

-- an accepted row (alt 120), then the client roles see none (RLS on, no policy)
insert into public.admin_promo_banners (image_url, link_url, alt, position) values ('https://x/a.webp', 'https://x', repeat('a', 120), 1);
select pg_temp.expect('TC-25 placement defaults to top', 'top'::text, (select placement from public.admin_promo_banners));
set local role anon;
select count(*) as anon_seen from public.admin_promo_banners \gset
reset role;
set local role authenticated;
select count(*) as auth_seen from public.admin_promo_banners \gset
reset role;
select pg_temp.expect('TC-18 anon reads nothing', 0::bigint, :anon_seen::bigint);
select pg_temp.expect('TC-18 authenticated reads nothing', 0::bigint, :auth_seen::bigint);

-- no TEST row is left: the test's own transaction rolls back
rollback;
