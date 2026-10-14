-- One dish name per seller, ignoring case and surrounding spaces.
-- 2026-10-14 a seller retried a failing photo upload and every retry created a new
-- "Creamy leche flan". The menu modal now checks names before saving; this index is
-- the backstop for double-taps and direct API calls (23505 → 409 in apis/sellers.py).
--
-- Fails if duplicates already exist: remove them first (both projects):
--   select seller_id, lower(btrim(name)), count(*) from public.food_items
--   group by 1, 2 having count(*) > 1;
create unique index if not exists uniq_food_items_seller_name
  on public.food_items (seller_id, lower(btrim(name)));
