-- ============================================================
-- AllinGo wallet low alert (docs/dev/20261110-allingo-wallet, T162). The backend reads the wallet every 30 minutes
-- (the Monitoring page can pause it or change how often) and tells the admins when it is below the threshold.
-- Only inserts: no table, index, constraint or function changes.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('allingo_wallet_alert_vnd', '500000'::jsonb,
   'Alert the team when the AllinGo delivery wallet is below this amount (VND), so it can be topped up before trips fail.'),
  ('allingo_wallet_alert_repeat_hours', '6'::jsonb,
   'While the AllinGo delivery wallet stays below the alert amount, repeat the alert every this many hours.')
on conflict (key) do nothing;

insert into public.metrics_job_health (job, interval_seconds) values
  ('allingo_wallet', 1800)
on conflict (job) do nothing;
