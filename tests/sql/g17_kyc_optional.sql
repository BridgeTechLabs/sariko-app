begin;
-- G17 admin fills in seller KYC (20261124200000_onboarding_existing_seller_optional.sql, flow 20261124-seller-kyc-admin
-- TC-19): the migration runs twice; an existing_seller row without agreement / bank / phone / pickup address is
-- taken, a /join row losing any of them is refused by the CHECK.
\ir _fixtures.sql

\ir ../../backend/supabase/migrations/20261124200000_onboarding_existing_seller_optional.sql
\ir ../../backend/supabase/migrations/20261124200000_onboarding_existing_seller_optional.sql

select pg_temp.t_seller('g17') as s \gset

insert into public.onboarding_applications (source, seller_profile_id, status, full_name, date_of_birth, nationality,
    id_type, id_number, email, residential_address, store_name, menu, tier)
  values ('existing_seller', :'s', 'approved', 'TEST sql g17', '1990-01-01', 'Philippines', 'passport', 'P1',
          'g17@example.invalid', 'x', 'TEST sql g17', '[]', 'community');
select pg_temp.expect('TC-19 existing_seller row without agreement / bank / phone / pickup address taken', 1::bigint,
  (select count(*) from public.onboarding_applications
    where seller_profile_id = :'s' and agreement_version is null and agreed_at is null and signature_name is null
      and bank_name is null and bank_account_number is null and bank_account_holder is null and phone is null
      and pickup_address is null));

insert into public.onboarding_applications (source, status, full_name, date_of_birth, nationality, id_type, id_number,
    email, residential_address, store_name, menu, tier, agreement_version, agreed_at, signature_name, bank_name,
    bank_account_number, bank_account_holder, phone, pickup_address)
  values ('join', 'submitted', 'TEST sql g17', '1990-01-01', 'Philippines', 'passport', 'P1', 'g17@example.invalid',
          'x', 'TEST sql g17', '[]', 'community', '20261023', now(), 'TEST sql g17', 'VCB', '0123456789', 'TEST',
          '+84901234567', 'x')
  returning id as j \gset

select pg_temp.expect_error('TC-19 join row without ' || c,
                            format('update public.onboarding_applications set %I = null where id = %L', c, :'j'),
                            '%onboarding_applications_join_complete_check%')
  from unnest(array['agreement_version', 'agreed_at', 'signature_name', 'bank_name', 'bank_account_number',
                    'bank_account_holder', 'phone', 'pickup_address']) c;

-- no TEST row is left: the test's own transaction rolls back
rollback;
