-- ============================================================
-- Rename history_api_metrics → metrics_api (Jack 2026-10-27): table prefixes name the purpose; history_* is the
-- audit trail kept long term, these are 5-minute monitoring rows deleted after api_metrics_retention_days.
-- 20261027000000 is already on develop, so it stays as is and this renames. RLS and the rows go with the table.
-- ============================================================

alter table if exists public.history_api_metrics rename to metrics_api;
alter index if exists public.history_api_metrics_bucket_start_idx rename to metrics_api_bucket_start_idx;
comment on table public.metrics_api is
  'API response times per 5-minute bucket, method, route pattern and status class (docs/dev/monitoring). No personal data.';
