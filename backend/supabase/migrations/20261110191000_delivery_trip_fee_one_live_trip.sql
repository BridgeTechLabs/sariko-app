-- ============================================================
-- T180 (docs/dev/20261110-delivery-tech).
-- A12: deliveries.trip_fee = what the delivery company charges for the CURRENT trip (VND, the quote it was booked with;
--      a rebook overwrites the row and its fee). NULL for trips booked before this column. Shown in the admin order detail.
-- A26: at most one LIVE trip row per order (status not ended), so two Ready taps at once cannot record two trips: the
--      second insert fails and the app cancels the trip it booked. Ended rows (and a rebook, which rewrites its row) are
--      not limited. Read on DEV 2026-11-10: no unique index on order_id, 0 orders with more than one row; PROD read by
--      Jack with prod-deliveries-readonly.sql before this goes to main (must be 0 orders with several live rows).
-- ============================================================

alter table public.deliveries add column if not exists trip_fee numeric;

create unique index if not exists deliveries_one_live_trip_per_order on public.deliveries (order_id)
  where coalesce(status, '') not in ('COMPLETED', 'CANCELLED', 'CANCELED', 'REJECTED', 'EXPIRED', 'LOST');
