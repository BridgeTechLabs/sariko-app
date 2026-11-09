-- ============================================================
-- Background job control from the admin Monitoring page (docs/dev/20261106-job-control). metrics_job_health keeps one row
-- per job (still never cleaned) and now also its settings: an admin can pause / resume a job and change how often it runs.
-- The backends read paused + interval_seconds every 15 seconds; their run records only update the last_* / failures
-- columns. The 4 rows are made here with the intervals the code used so far (60 / 120 / 300 / 600 seconds).
-- ============================================================

alter table public.metrics_job_health
  add column if not exists paused boolean not null default false,
  add column if not exists paused_at timestamptz,
  add constraint metrics_job_health_interval_check check (interval_seconds between 60 and 86400);

insert into public.metrics_job_health (job, interval_seconds) values
  ('order_expiry', 60),
  ('payment_reconcile', 120),
  ('api_metrics', 300),
  ('payout_auto', 600)
on conflict (job) do nothing;
