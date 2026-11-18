-- ============================================================
-- Invoices — sequential invoice_no. id stays uuid.
-- Existing rows get an invoice_no too.
-- ============================================================

alter table public.invoices
  add column if not exists invoice_no bigint generated always as identity;

alter table public.invoices
  add constraint invoices_invoice_no_key unique (invoice_no);
