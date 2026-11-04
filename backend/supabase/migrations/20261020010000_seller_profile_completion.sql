-- ============================================================
-- Existing sellers complete their seller profile (spec docs/dev/seller-profile-completion).
-- Identity / tax / agreement of a seller who never went through /join go into the same
-- onboarding_applications table as /join, linked by seller_profile_id (one KYC source for
-- the admin review and the tax report T43). Operational fields (bank, phone, pickup
-- address) stay in seller_profiles, where payouts and Lalamove read them.
--   * source: 'join' (public form) or 'existing_seller' (in-app form), at most one
--     existing_seller row per seller.
--   * id_expiry_date: NĐ 248/2026 Đ18.1.b (passport valid at least N months, N in
--     admin_settings onboarding_min_id_validity_months). Null on rows from before this.
--   * personal_data_consent_at: consent to personal data processing (Luật 91/2025 Đ19.1).
--   * tier: an existing seller keeps their current plan, which may be founding / bodega,
--     so the 4-plan check becomes a FK to admin_tier_config (/join still only offers 4).
-- Expand-only: the running backend writes none of the new columns.
-- ============================================================

alter table public.onboarding_applications
  add column if not exists source text not null default 'join',
  add column if not exists id_expiry_date date,
  add column if not exists personal_data_consent_at timestamp with time zone;

alter table public.onboarding_applications drop constraint if exists onboarding_applications_source_check;
alter table public.onboarding_applications
  add constraint onboarding_applications_source_check check (source in ('join', 'existing_seller'));

alter table public.onboarding_applications drop constraint if exists onboarding_applications_tier_check;
alter table public.onboarding_applications drop constraint if exists onboarding_applications_tier_fkey;
alter table public.onboarding_applications
  add constraint onboarding_applications_tier_fkey foreign key (tier) references public.admin_tier_config (tier);

create unique index if not exists onboarding_applications_existing_seller_uidx
  on public.onboarding_applications (seller_profile_id) where source = 'existing_seller';
create index if not exists onboarding_applications_seller_idx
  on public.onboarding_applications (seller_profile_id);

insert into public.admin_settings (key, value, description) values
  ('onboarding_min_id_validity_months', '6'::jsonb,
   'A passport must still be valid for at least this many months on the day the seller submits (NĐ 248/2026 Đ18.1.b). Expired ID documents are always refused.')
on conflict (key) do nothing;
