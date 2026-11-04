-- ============================================================
-- Invoices — sequential invoice_no; request_id becomes SARIKO-<invoice_no padded to 11 digits>
-- (e.g. invoice_no 4 → SARIKO-00000000004). id stays uuid.
-- Existing rows get an invoice_no but keep their request_id (it may already be on VNPAY's side).
-- ============================================================

alter table public.invoices
  add column if not exists invoice_no bigint generated always as identity;

alter table public.invoices
  add constraint invoices_invoice_no_key unique (invoice_no);

-- Identity values are assigned before BEFORE triggers run, so new.invoice_no is set here.
create or replace function public.set_invoices_request_id () returns trigger
  language plpgsql
as $$
begin
  if new.request_id is null then
    new.request_id = 'SARIKO-' || lpad(new.invoice_no::text, 11, '0');
  end if;
  return new;
end;
$$;

drop trigger if exists on_invoices_insert_request_id on public.invoices;
create trigger on_invoices_insert_request_id
  before insert on public.invoices
  for each row
  execute function public.set_invoices_request_id ();
