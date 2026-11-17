-- T178 (docs/dev/20261110-reason-texts): orders.cancellation_reason now holds a code (seller_timeout, no_driver,
-- seller_reject_other, admin_cancel, ...) that each viewer's app translates. Text a person typed (a seller's "other"
-- reason, an admin's cancel reason) goes here; the buyer's reads never select it. Rows before T178 keep their
-- sentence in cancellation_reason and are shown as written.
alter table public.orders add column if not exists cancellation_note text;

-- PostgREST must see the new column before the backends select it
notify pgrst, 'reload schema';
