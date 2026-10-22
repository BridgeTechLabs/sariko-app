-- ============================================================
-- Pre-launch page (docs/dev/prelaunch): before this Vietnam date the buyer pages of
-- app.sariko.store redirect to /coming-soon; seller, sign-in, /join and legal pages stay open.
-- 99991231 = coming soon with no date announced. GET /rest/v1/launch reads it
-- (dao_admin_config.get_positive_int, default 99991231). Opening day = change the value on the admin.
-- Expand-only: the running backend ignores rows it doesn't know.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('public_launch_date', '99991231'::jsonb,
   'Public opening date of the marketplace (YYYYMMDD, Vietnam time). Before this date buyer pages show "Sariko is opening soon" and send buyers to /coming-soon; seller pages, sign-in, /join and legal pages stay open. 99991231 = coming soon, no date announced. Set to today or earlier to open.')
on conflict (key) do nothing;
