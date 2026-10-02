-- Mock data for DEV. Fabricated — no production rows, safe to commit.
--
-- Shaped after the 2026-09-29 production dump (which tables matter, which columns
-- are actually filled) but every value here is invented. Deliberately small: one
-- row per situation the app has to handle, not a copy of production's volume.
--
-- Fixed UUIDs so reruns are idempotent and ids can be pasted into URLs while
-- debugging. Every login below uses the password: devpassword123

begin;

-- ── Auth ────────────────────────────────────────────────────────────────────
-- Column list copied from the project's own auth schema. bcrypt via pgcrypto;
-- if a fresh project puts it elsewhere, drop the "extensions." prefix.
--
-- The token columns are nullable with no default, but GoTrue scans them into
-- plain Go strings: left NULL, every login/lookup of these users is a 500
-- "Database error loading user". A real signup writes '' — so do we.
insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
  is_sso_user, is_anonymous,
  confirmation_token, recovery_token, email_change, email_change_token_new,
  email_change_token_current, phone_change, phone_change_token, reauthentication_token
)
select
  '00000000-0000-0000-0000-000000000000', u.id, 'authenticated', 'authenticated',
  u.email, extensions.crypt('devpassword123', extensions.gen_salt('bf')), now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('fullname', u.name, 'is_seller', u.is_seller), now(), now(), false, false,
  '', '', '', '', '', '', '', ''
from (values
  ('11111111-1111-1111-1111-111111111111'::uuid, 'buyer@dev.local',   'Mai Buyer', false),
  ('22222222-2222-2222-2222-222222222222'::uuid, 'buyer2@dev.local',  'Nam Buyer', false),
  ('33333333-3333-3333-3333-333333333333'::uuid, 'seller@dev.local',  'Ate Rosa',  true),
  ('44444444-4444-4444-4444-444444444444'::uuid, 'seller2@dev.local', 'Kuya Ben',  true)
) as u(id, email, name, is_seller)
on conflict (id) do nothing;

-- ── Users ───────────────────────────────────────────────────────────────────
-- The on_auth_user_created trigger has already created these rows from the insert
-- above, but it only knows what auth carries: it cannot set role, phone or
-- preferred_language. Hence an upsert rather than "do nothing" — the latter would
-- silently keep the trigger's sparser row.
insert into public.users (id, email, name, phone, role, is_seller, preferred_language) values
  ('11111111-1111-1111-1111-111111111111', 'buyer@dev.local',   'Mai Buyer', '+84900000001', 'customer', false, 'vi'),
  ('22222222-2222-2222-2222-222222222222', 'buyer2@dev.local',  'Nam Buyer', '+84900000002', 'customer', false, 'en-PH'),
  ('33333333-3333-3333-3333-333333333333', 'seller@dev.local',  'Ate Rosa',  '+84900000003', 'seller',   true,  'en-PH'),
  ('44444444-4444-4444-4444-444444444444', 'seller2@dev.local', 'Kuya Ben',  '+84900000004', 'seller',   true,  'vi')
on conflict (id) do update set
  email = excluded.email, name = excluded.name, phone = excluded.phone,
  role = excluded.role, is_seller = excluded.is_seller,
  preferred_language = excluded.preferred_language;

insert into public.user_addresses (user_id, label, address, lat, lon, is_default) values
  ('11111111-1111-1111-1111-111111111111', 'Home',   '12 Nguyễn Huệ, Quận 1, TP.HCM',   10.7743, 106.7038, true),
  ('11111111-1111-1111-1111-111111111111', 'Office', '45 Lê Lợi, Quận 1, TP.HCM',       10.7729, 106.6984, false),
  ('22222222-2222-2222-2222-222222222222', 'Home',   '88 Phan Xích Long, Phú Nhuận',    10.7995, 106.6889, true);

-- ── Sellers ─────────────────────────────────────────────────────────────────
-- One active + listed (the only kind a buyer can order from) and one coming_soon,
-- because the home page and seller page render those two states differently.
insert into public.seller_profiles (
  id, user_id, store_name, slug, description, address, lat, lon,
  phone, tier, tax_category, status, is_open, is_verified, is_listed, display_order
) values
  ('aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',
   'Rosa Home Kitchen', 'rosa-home-kitchen', 'Filipino comfort food, cooked daily.',
   '30 Tôn Thất Thiệp, Quận 1, TP.HCM', 10.7731, 106.7010,
   '+84901000001', 'founding', 'goods', 'active', true, true, true, 1),
  ('aaaaaaaa-0000-0000-0000-000000000002', '44444444-4444-4444-4444-444444444444',
   'Ben BBQ Cart', 'ben-bbq-cart', 'Grilled skewers, weekends only.',
   '7 Hồ Tùng Mậu, Quận 1, TP.HCM', 10.7715, 106.7045,
   '+84901000002', 'community', 'goods', 'coming_soon', false, false, true, 2)
on conflict (id) do nothing;

-- ── Menu ────────────────────────────────────────────────────────────────────
insert into public.menu_categories (id, seller_id, name, sort_order, is_active) values
  ('bbbbbbbb-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'Mains',    1, true),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001', 'Desserts', 2, true),
  ('bbbbbbbb-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000002', 'Skewers',  1, true)
on conflict (id) do nothing;

-- price_text mirrors what apis/sellers.py:_make_price_text() writes.
-- cccc…01 carries variants, so its own price is never charged — see the migration
-- header for why the column still has to hold something.
insert into public.food_items (
  id, seller_id, category_id, name, description, price, price_text, unit_label,
  min_quantity, quantity_step, preorder_day, is_available, is_featured
) values
  ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
   'Chicken Adobo', 'Slow-braised in soy and vinegar.', 90000, '90.000 ₫', 'phần', 1, 1, 0, true, true),
  ('cccccccc-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
   'Pancit Bihon', 'Rice noodles with vegetables.', 75000, '75.000 ₫', 'phần', 1, 1, 0, true, false),
  ('cccccccc-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
   'Buko Salad', 'Young coconut, needs a day ahead.', 60000, '60.000 ₫', 'hộp', 1, 1, 1, true, true),
  ('cccccccc-0000-0000-0000-000000000004', 'aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
   'Leche Flan', 'Sold out right now.', 45000, '45.000 ₫', 'hộp', 1, 1, 0, false, false),
  ('cccccccc-0000-0000-0000-000000000005', 'aaaaaaaa-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000003',
   'Pork BBQ Skewer', 'Charcoal grilled.', 25000, '25.000 ₫', 'xiên', 2, 1, 0, true, false)
on conflict (id) do nothing;

-- Same path apis/sellers.py writes: food-items/{seller_id}/{item_id}. The files
-- themselves are put there by scripts/copy_images_to_dev.sh — a db reset empties
-- storage, so run it after every reset. Host is the dev project's.
update public.food_items
set image_url = 'https://saphxhqpjrhdsqbtnwqe.supabase.co/storage/v1/object/public/sariko-public/food-items/'
  || seller_id || '/' || id
where id::text like 'cccccccc-0000-0000-0000-%';

-- ── Price variants ──────────────────────────────────────────────────────────
-- Chicken Adobo gets three levels, one of them sold out: the range shown on the
-- menu must skip it, and adding it to the cart must be refused.
insert into public.food_item_variants (id, food_item_id, name, price, price_text, sort_order, is_available) values
  ('dddddddd-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001', 'S',  60000,  '60.000 ₫', 0, true),
  ('dddddddd-0000-0000-0000-000000000002', 'cccccccc-0000-0000-0000-000000000001', 'M',  90000,  '90.000 ₫', 1, true),
  ('dddddddd-0000-0000-0000-000000000003', 'cccccccc-0000-0000-0000-000000000001', 'L',  130000, '130.000 ₫', 2, false)
on conflict (id) do nothing;

-- ── Orders ──────────────────────────────────────────────────────────────────
-- Three of them so the buyer history and the seller dashboard both have something
-- in every state the status machine can be in mid-flow.
-- Money follows the real formula: vat is charged on the commission, and the
-- payout excludes the delivery fee.
insert into public.orders (
  id, user_id, seller_id, seller_user_id, status, payment_status, delivery_method,
  delivery_address, delivery_lat, delivery_lon, subtotal, delivery_fee, total_amount,
  commission_rate, commission_amount, vat_rate, vat_amount, payout_amount, note
) values
  -- paid, delivered, one line with a variant
  ('eeeeeeee-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',
   'done', 'paid', 'delivery', '12 Nguyễn Huệ, Quận 1, TP.HCM', 10.7743, 106.7038,
   150000, 25000, 175000, 0.10, 15000, 0.10, 1500, 133500, null),
  -- awaiting payment: the Pay Now retry path
  ('eeeeeeee-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',
   'aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',
   'pending', 'pending', 'delivery', '45 Lê Lợi, Quận 1, TP.HCM', 10.7729, 106.6984,
   75000, 20000, 95000, 0.10, 7500, 0.10, 750, 66750, 'Ít ớt giúp em'),
  -- paid and waiting on the seller: Accept/Reject on the dashboard
  ('eeeeeeee-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222',
   'aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',
   'confirmed', 'paid', 'delivery', '88 Phan Xích Long, Phú Nhuận', 10.7995, 106.6889,
   60000, 22000, 82000, 0.10, 6000, 0.10, 600, 53400, null)
on conflict (id) do nothing;

-- price_snapshot is the FINAL unit price: for a variant line it is the variant's
-- price, not food_items.price. subtotal above equals the sum of these lines.
insert into public.order_items (order_id, food_item_id, name_snapshot, price_snapshot, unit_label_snapshot, variant_name_snapshot, quantity) values
  ('eeeeeeee-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001', 'Chicken Adobo', 60000, 'phần', 'S', 1),
  ('eeeeeeee-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001', 'Chicken Adobo', 90000, 'phần', 'M', 1),
  ('eeeeeeee-0000-0000-0000-000000000002', 'cccccccc-0000-0000-0000-000000000002', 'Pancit Bihon',  75000, 'phần', null, 1),
  ('eeeeeeee-0000-0000-0000-000000000003', 'cccccccc-0000-0000-0000-000000000003', 'Buko Salad',    60000, 'hộp',  null, 1);

insert into public.payments (order_id, amount, status, method) values
  ('eeeeeeee-0000-0000-0000-000000000001', 175000, 'succeeded', 'vnpay'),
  ('eeeeeeee-0000-0000-0000-000000000003', 82000,  'succeeded', 'vnpay');

-- ── Reviews ─────────────────────────────────────────────────────────────────
-- One overall row (food_item_id null) + one per-dish row, the exact shape
-- apis/reviews.py writes. The on_review_change trigger recomputes rating_avg on
-- both seller_profiles and food_items, so those are never set by hand here.
insert into public.reviews (order_id, seller_id, user_id, food_item_id, rating, comment) values
  ('eeeeeeee-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
   '11111111-1111-1111-1111-111111111111', null, 5, null),
  ('eeeeeeee-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
   '11111111-1111-1111-1111-111111111111', 'cccccccc-0000-0000-0000-000000000001', 5, 'Ngon, đúng vị nhà làm.');

commit;
