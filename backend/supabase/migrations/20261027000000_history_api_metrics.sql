-- ============================================================
-- How long each API takes (docs/dev/monitoring Q1, T135). The backend counts every request in memory
-- (except /health) per method, route pattern (e.g. /rest/v1/orders/{order_id}) and status class, and every
-- 5 minutes writes one row per group: count, p50 / p95 / max in whole ms. No IP, user or query string.
-- Rows older than api_metrics_retention_days are deleted once a day. The admin Monitoring page reads them
-- and marks a route "slow" when its p95 is above api_slow_ms.
-- ============================================================

create table if not exists public.history_api_metrics (
  id            bigint generated always as identity primary key,
  bucket_start  timestamptz not null,
  method        text        not null,
  route         text        not null,
  status_class  text        not null check (status_class in ('2xx', '3xx', '4xx', '5xx')),
  count         integer     not null check (count > 0),
  p50_ms        integer     not null,
  p95_ms        integer     not null,
  max_ms        integer     not null,
  created_at    timestamptz not null default now()
);
create index if not exists history_api_metrics_bucket_start_idx on public.history_api_metrics (bucket_start);
alter table public.history_api_metrics enable row level security;   -- service role only (backends)
comment on table public.history_api_metrics is
  'API response times per 5-minute bucket, method, route pattern and status class (docs/dev/monitoring). No personal data.';

insert into public.admin_settings (key, value, description) values
  ('api_slow_ms', '1000'::jsonb,
   'Milliseconds (integer > 0): an API whose p95 response time is above this is marked "slow" on the admin Monitoring page.'),
  ('api_metrics_retention_days', '30'::jsonb,
   'Days (integer > 0) of API response-time rows kept in history_api_metrics; older rows are deleted once a day.')
on conflict (key) do nothing;
