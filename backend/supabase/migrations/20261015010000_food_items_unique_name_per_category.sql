-- DEV only in practice. 20261015000000 first shipped as one name per seller
-- (uniq_food_items_seller_name) and was applied on dev, but prod rejected it because a
-- seller legitimately lists the same dish in two categories. That migration now creates
-- the per-category index instead; this one moves dev onto it. On prod both statements
-- are no-ops (the old index never existed, the new one was just created).
drop index if exists public.uniq_food_items_seller_name;
create unique index if not exists uniq_food_items_seller_category_name
  on public.food_items (seller_id, category_id, lower(btrim(name)));
