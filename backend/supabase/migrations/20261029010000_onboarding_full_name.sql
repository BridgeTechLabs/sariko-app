-- ============================================================
-- One "Full name" box instead of first + last name (docs/dev/seller-full-name N1): sellers left out the
-- middle name, so the bank account holder never matched. Every row gets full_name (older rows: first + last,
-- the name check ignores word order); first_name / last_name stay unread until a later migration drops them
-- once the app and admin that read full_name are on PROD. Re-runnable: a full_name already set is kept.
-- ============================================================

alter table public.onboarding_applications add column if not exists full_name text;
update public.onboarding_applications
   set full_name = btrim(regexp_replace(coalesce(first_name, '') || ' ' || coalesce(last_name, ''), '\s+', ' ', 'g'))
 where full_name is null;
alter table public.onboarding_applications alter column full_name set not null;
alter table public.onboarding_applications alter column first_name drop not null;
alter table public.onboarding_applications alter column last_name drop not null;
comment on column public.onboarding_applications.full_name is
  'Full name exactly as on the ID. The signature and the bank account holder must have the same words (any order).';
