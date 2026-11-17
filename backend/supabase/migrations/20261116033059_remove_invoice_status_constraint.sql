-- ============================================================
-- Invoices — status 'generating' and one active invoice per order (sariko-admin-panel services/invoice_service).
-- Lifecycle: initial (the admin export inserted it, queued, not sent to VNPAY yet)
--   → generating (the worker took it, being sent to VNPAY)
--   → issued | failed | pending (VNPAY did not answer: outcome unknown, checked by hand); cancelled unchanged.
-- The status check is dropped: the values are only written by the admin backend.
-- An order keeps one active invoice (any status but failed / cancelled); one whose invoices all failed or were
-- cancelled can be invoiced again, with a new row (new request_id).
-- ============================================================

alter table public.invoices
  drop constraint if exists invoices_status_check;

-- was `order_id uuid not null unique` (20261106130000_add_order_id_to_invoices.sql)
alter table public.invoices
  drop constraint if exists invoices_order_id_key;

create unique index if not exists invoices_order_id_active_key on public.invoices using btree (order_id)
  where status not in ('failed', 'cancelled');

drop index if exists public.idx_invoices_status;
create index if not exists idx_invoices_status on public.invoices using btree (status);
