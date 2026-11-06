-- ============================================================
-- Background job health (docs/dev/20261106-job-health). One row per job, not a time series, never cleaned:
-- every run of a background loop (app: order_expiry, payment_reconcile, api_metrics; admin: payout_auto) upserts
-- its row. The admin Monitoring page reads it. After job_alert_failures failed runs in a row the team gets one
-- Zalo message, and one more when the job runs again.
-- ============================================================

create table if not exists public.metrics_job_health (
  job               text        primary key,
  interval_seconds  integer     not null,
  last_run_at       timestamptz,
  last_ok_at        timestamptz,
  last_error        text,
  last_error_at     timestamptz,
  failures          integer     not null default 0
);
alter table public.metrics_job_health enable row level security;   -- service role only (backends)
comment on table public.metrics_job_health is
  'One row per background job: last run, last success, last error, failed runs in a row (docs/dev/20261106-job-health). Never cleaned.';

insert into public.admin_settings (key, value, description) values
  ('job_alert_failures', '3'::jsonb,
   'Failed runs in a row (integer > 0) of a background job before the team gets a Zalo message.')
on conflict (key) do nothing;
