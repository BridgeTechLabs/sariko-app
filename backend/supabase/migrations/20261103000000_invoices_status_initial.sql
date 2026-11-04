-- ============================================================
-- Invoices — new status 'initial': the row exists on our side but has not been sent to VNPAY yet.
-- Lifecycle: initial → pending (being sent / sent but timed out, outcome unknown) → issued | failed;
-- cancelled unchanged.
-- ============================================================

alter table public.invoices
  drop constraint if exists invoices_status_check;

alter table public.invoices
  add constraint invoices_status_check check (
    (status = any (array['initial'::text, 'pending'::text, 'issued'::text, 'failed'::text, 'cancelled'::text]))
  );

alter table public.invoices
  alter column status set default 'initial'::text;

-- An 'initial' row left behind (process died before sending) needs a look too, like pending / failed.
drop index if exists public.idx_invoices_status;
create index if not exists idx_invoices_status on public.invoices using btree (status)
  where status in ('initial', 'pending', 'failed');
