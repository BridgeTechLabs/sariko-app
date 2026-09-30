-- Enable RLS on the five tables rls.sql never mentions.
--
-- Production does not need them listed: it has an event trigger, ensure_rls, that
-- fires on every CREATE TABLE and turns RLS on by itself (see pg_event_trigger —
-- owner supabase_admin, not postgres). That trigger cannot be recreated from a
-- migration: creating event triggers requires superuser, which the postgres role
-- on hosted Supabase is not.
--
-- So a project built from these migrations comes up LESS protected than
-- production: no ensure_rls, therefore RLS off on anything rls.sql forgot. Listing
-- them explicitly closes the gap and does not depend on any trigger.
--
-- No policies are added: every one of these tables is read and written by the
-- backend with the service_role key, which bypasses RLS. With RLS on and no
-- policy, anon and authenticated get nothing — the posture we want, since the
-- anon key ships inside the frontend bundle.

alter table public.user_addresses  enable row level security;  -- delivery addresses: PII
alter table public.refunds         enable row level security;
alter table public.admin_payouts   enable row level security;
alter table public.admin_tier_config enable row level security;  -- commission rates
alter table public.admin_tax_config  enable row level security;
