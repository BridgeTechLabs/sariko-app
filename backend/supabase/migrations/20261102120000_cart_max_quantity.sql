-- Cap on one cart row (dish + price option), checked at POST /cart/add, PATCH /cart/update and POST /orders.
-- On PROD a bot placed unpaid orders of ~22 billion ₫ each: nothing limited the quantity.
insert into public.admin_settings (key, value, description)
values
  ('cart_max_quantity_per_item', '50'::jsonb,
   'Maximum quantity of one dish (one price option) in a cart or order (integer > 0). A larger quantity is refused when the buyer adds it, changes it or places the order.')
on conflict (key) do nothing;
