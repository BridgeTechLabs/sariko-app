-- ============================================================
-- Invoices — VNPAY Invoice (viiAPI) e-invoices issued to a seller.
-- One invoice groups several orders of that seller through invoice_orders.
-- Adjustment / replacement invoices point back to the original through ref_request_id.
-- request_id is the idempotency key sent to VNPAY (globally unique there too).
-- Columns hold what we filter / join / reconcile on; the full request payload
-- and VNPAY's responses / webhook events live in snapshot_data.
-- ============================================================

create table if not exists public.invoices (
  id uuid not null default gen_random_uuid (),
  seller_id uuid not null,
  request_id text not null,
  kind text not null default 'original'::text,
  ref_request_id text null,
  tax_code text not null,
  invoice_type text not null,
  invoice_symbol text null,
  invoice_number text null,
  invoice_created_date date null,
  lookup_code text null,
  tax_authority_code text null,
  status text not null default 'pending'::text,
  vnpay_status text null,
  invoice_status text null,
  tvan_status text null,
  sign_status text null,
  total_amount_after_tax numeric null,
  error_code text null,
  error_message text null,
  trace_id text null,
  snapshot_data jsonb not null default '{}'::jsonb,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  issued_at timestamp with time zone null,
  constraint invoices_pkey primary key (id),
  constraint invoices_request_id_key unique (request_id),
  constraint invoices_seller_id_fkey foreign key (seller_id) references seller_profiles (id),
  constraint invoices_kind_check check (
    (kind = any (array['original'::text, 'adjustment'::text, 'replacement'::text]))
  ),
  constraint invoices_ref_request_id_check check (
    ((kind = 'original'::text) = (ref_request_id is null))
  ),
  constraint invoices_status_check check (
    (status = any (array['pending'::text, 'issued'::text, 'failed'::text, 'cancelled'::text]))
  )
) TABLESPACE pg_default;

create index if not exists idx_invoices_seller_id on public.invoices using btree (seller_id);
create index if not exists idx_invoices_status on public.invoices using btree (status)
  where status in ('pending', 'failed');

create or replace function public.set_invoices_updated_at () returns trigger
  language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_invoices_update on public.invoices;
create trigger on_invoices_update
  before update on public.invoices
  for each row
  execute function public.set_invoices_updated_at ();

-- ============================================================
-- Invoice orders — which orders an invoice covers.
-- active = false once the invoice is failed / cancelled, so its orders can be invoiced again;
-- the partial unique index keeps an order in at most one active invoice.
-- ============================================================

create table if not exists public.invoice_orders (
  invoice_id uuid not null,
  order_id uuid not null,
  active boolean not null default true,
  created_at timestamp with time zone not null default now(),
  constraint invoice_orders_pkey primary key (invoice_id, order_id),
  constraint invoice_orders_invoice_id_fkey foreign key (invoice_id) references invoices (id) on delete cascade,
  constraint invoice_orders_order_id_fkey foreign key (order_id) references orders (id)
) TABLESPACE pg_default;

create unique index if not exists idx_invoice_orders_active_order_id on public.invoice_orders using btree (order_id)
  where active;

-- Backend-only tables (service_role bypasses RLS); no policies → anon/authenticated get nothing.
alter table public.invoices enable row level security;
alter table public.invoice_orders enable row level security;
