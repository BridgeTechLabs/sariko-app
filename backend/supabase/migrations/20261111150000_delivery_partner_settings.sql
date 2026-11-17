-- ============================================================
-- T192 C (docs/dev/20261111-admin-settings-pages): the Delivery Partner page of the admin app.
-- 1. Which companies AllinGo may book (0 / 1, read by the app on every quote and booking; Jack 11/11: no Lalamove
--    through AllinGo). on conflict do nothing: a value an admin changed is never overwritten.
-- 2. Three descriptions without "Lalamove": they also apply to AllinGo trips.
-- 3. deliveries.allingo_partner: the company AllinGo booked for the current trip (null for Lalamove trips and for a
--    trip AllinGo has not given a company yet); a rebook overwrites it. Booking and driver times come from
--    history_delivery (changed_at), which log_delivery already writes; it does not look at this column.
-- deliveries: a new nullable column only, no index / constraint / trigger change.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('allingo_partner_grab', '1'::jsonb, '1 = AllinGo may book this company, 0 = never'),
  ('allingo_partner_gsm', '1'::jsonb, '1 = AllinGo may book this company, 0 = never'),
  ('allingo_partner_lalamove', '0'::jsonb, '1 = AllinGo may book this company, 0 = never')
on conflict (key) do nothing;

update public.admin_settings set description =
  'Minutes (integer > 0) an order may stay delivery_failed (the delivery company could not deliver) before the buyer may cancel it for a full refund.'
where key = 'buyer_cancel_late_delivery_failed_minutes';
update public.admin_settings set description =
  'Times (integer > 0) a seller may rebook a driver after a trip fails; after that the seller cancels (full refund) or delivers themselves.'
where key = 'seller_rebook_max';
update public.admin_settings set description =
  'Tries (integer > 0) to book a driver when the seller taps Ready; if all fail the order is cancelled with a full refund.'
where key = 'driver_booking_attempts';

alter table public.deliveries add column if not exists allingo_partner text;
