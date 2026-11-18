-- ============================================================
-- sariko-private: private bucket for backend-only files (first use: invoice PDFs).
-- public = false and no storage.objects policies → anon / authenticated can neither list, read
-- nor write; the backend's service role bypasses RLS. Readers get a signed URL from the backend.
-- ============================================================

insert into storage.buckets (id, name, public) values
  ('sariko-private', 'sariko-private', false)
on conflict (id) do nothing;

-- Invoices — where the invoice's PDF is stored in sariko-private (null = not stored yet).
alter table public.invoices
  add column if not exists pdf_path text null;
