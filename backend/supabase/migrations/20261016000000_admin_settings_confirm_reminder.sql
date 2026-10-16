-- ============================================================
-- How long before a paid, unaccepted order auto-cancels the seller gets a
-- reminder push (services/order_expiry.py). Expand-only: the backend falls back
-- to 10 if the row is missing.
-- ============================================================

insert into public.admin_settings (key, value, description)
values ('order_confirm_reminder_minutes', '10'::jsonb,
        'Minutes (integer > 0) before a paid order auto-cancels (order_confirm_minutes) that the seller gets a reminder push to accept it. Sent once per order.')
on conflict (key) do nothing;
