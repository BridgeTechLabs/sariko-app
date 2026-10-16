-- ============================================================
-- Order time windows and retry counts an admin can change without a deploy
-- (admin repo settings page). Same shape as order_confirm_minutes: integer > 0; the backend
-- reads them on every use and falls back to the default below if a row is
-- missing or invalid (dao_admin_config.get_positive_int).
-- Expand-only: the running backend ignores rows it doesn't know.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('buyer_cancel_late_confirmed_minutes', '60'::jsonb,
   'Minutes (integer > 0) after the seller accepts an order (scheduled: after the delivery time) before the buyer may cancel it for a full refund if it is still not Ready.'),
  ('buyer_cancel_late_delivery_failed_minutes', '30'::jsonb,
   'Minutes (integer > 0) an order may stay delivery_failed (Lalamove could not deliver) before the buyer may cancel it for a full refund.'),
  ('buyer_cancel_before_appointment_minutes', '1440'::jsonb,
   'A scheduled order still waiting for the seller can be cancelled by the buyer only up to this many minutes (integer > 0) before the delivery time.'),
  ('seller_rebook_max', '3'::jsonb,
   'Times (integer > 0) a seller may rebook a Lalamove driver after a trip fails; after that the seller cancels (full refund) or delivers themselves.'),
  ('driver_booking_attempts', '3'::jsonb,
   'Tries (integer > 0) to book a Lalamove driver when the seller taps Ready; if all fail the order is cancelled with a full refund.')
on conflict (key) do nothing;
