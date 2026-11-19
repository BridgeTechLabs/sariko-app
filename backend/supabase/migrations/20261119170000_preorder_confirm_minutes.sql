-- ============================================================
-- How long a seller has to accept a paid pre-order (services/order_expiry.py).
-- Expand-only: the backend falls back to 720 if the row is missing.
-- ============================================================

insert into public.admin_settings (key, value, description)
values ('preorder_confirm_minutes', '720'::jsonb,
        'Minutes (integer > 0) a seller has to accept a paid pre-order (an order with a pre-order dish) before it is cancelled and refunded. Counted from payment, open or closed, never past the delivery time. Same-day orders use order_confirm_minutes.')
on conflict (key) do nothing;
