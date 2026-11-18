-- ============================================================
-- Invoices — new status 'initial': the row exists on our side but has not been sent to VNPAY yet.
-- An insert without a status gets 'initial'. Status values are not checked by the database.
-- ============================================================

-- The check from 20261029031531_create_invoices.sql does not allow 'initial'.
alter table public.invoices
  drop constraint if exists invoices_status_check;

alter table public.invoices
  alter column status set default 'initial'::text;
