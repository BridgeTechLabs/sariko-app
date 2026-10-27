-- ============================================================
-- Enterprise is invitation only, capped at this many sellers (T101).
-- /join shows the places left and POST /onboarding/applications answers 409 enterprise_full
-- once seller_profiles on the enterprise tier reach it. Integer > 0; the backend falls back
-- to 5 if the row is missing or invalid. Expand-only: the running backend ignores it.
-- ============================================================

insert into public.admin_settings (key, value, description)
values
  ('enterprise_slots', '5'::jsonb,
   'Maximum number of sellers on the Enterprise plan (integer > 0). Enterprise is by invitation; when this many sellers are on it, the join form shows the plan as full and rejects new Enterprise applications.')
on conflict (key) do nothing;
