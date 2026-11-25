-- ============================================================
-- An operator fills in a seller's ID / tax / bank on the admin app (docs/dev/20261124-seller-kyc-admin QĐ-10).
-- The existing_seller row it creates has no agreement yet (only the seller signs, in the app) and may have no bank,
-- phone or pickup address yet: those 8 columns may be null on such a row. A /join row stays as strict as before
-- (the CHECK below). Re-runnable.
-- ============================================================

alter table public.onboarding_applications
  alter column agreement_version drop not null,
  alter column agreed_at drop not null,
  alter column signature_name drop not null,
  alter column bank_name drop not null,
  alter column bank_account_number drop not null,
  alter column bank_account_holder drop not null,
  alter column phone drop not null,
  alter column pickup_address drop not null;

alter table public.onboarding_applications drop constraint if exists onboarding_applications_join_complete_check;
alter table public.onboarding_applications
  add constraint onboarding_applications_join_complete_check check (
    source <> 'join' or (
      agreement_version is not null and agreed_at is not null and signature_name is not null
      and bank_name is not null and bank_account_number is not null and bank_account_holder is not null
      and phone is not null and pickup_address is not null));
