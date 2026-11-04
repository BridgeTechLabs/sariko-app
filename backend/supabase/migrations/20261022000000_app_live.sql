-- ============================================================
-- Go-live switch (docs/dev/prelaunch): while app_live = 0 the buyer pages of app.sariko.store
-- redirect to /coming-soon; seller, sign-in, /join and legal pages stay open. app_live = 1 = live.
-- launch_date is only the "open from" date shown on that page (99991231 = hidden); reaching it
-- does not go live. GET /rest/v1/launch reads both (dao_admin_config; app_live 0..1, default 0).
-- Go live = admin turns app_live on on the Danger Zone page.
-- Expand-only: the running backend ignores rows it doesn't know.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('app_live', '0'::jsonb,
   'Go-live switch: 0 = not live yet, buyer pages of the app redirect to "Sariko is opening soon" (seller pages, sign-in, /join and legal pages stay open); 1 = live, open for sales. Only this key decides the redirect.'),
  ('launch_date', '99991231'::jsonb,
   'Opening date shown on the coming-soon page as "Open from dd/MM/yyyy" (YYYYMMDD, Vietnam time). 99991231 = no date shown. Display only: reaching this date does not go live.')
on conflict (key) do nothing;
