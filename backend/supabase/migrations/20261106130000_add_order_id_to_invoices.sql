-- ============================================================
-- Invoices — one invoice per order (replaces invoice_orders).
-- ============================================================

alter table public.invoices
  add column if not exists order_id uuid not null unique references public.orders (id);