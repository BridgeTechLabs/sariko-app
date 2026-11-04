-- ============================================================
-- The receiver of a delivery order (docs/dev/delivery-recipient R1): the Lalamove driver calls the
-- receiver of the chosen address, not the buyer's profile, and reads the house number / floor / note.
-- Nullable, no backfill: orders placed before keep using the buyer's profile.
-- ============================================================

alter table public.orders
  add column if not exists receiver_name text,
  add column if not exists receiver_phone text,
  add column if not exists delivery_note text;

comment on column public.orders.receiver_name is 'Delivery orders: who the driver hands the food to. NULL = the buyer (orders before 2026-10-30).';
comment on column public.orders.receiver_phone is 'Delivery orders: the receiver''s phone, E.164 (+84...). NULL = the buyer''s profile phone.';
comment on column public.orders.delivery_note is 'Delivery orders: house number / floor and the note for the driver, sent ahead of the address.';
