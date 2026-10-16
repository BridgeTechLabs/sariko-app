-- Seller applications from the public /join form (TODO T40 seller verification,
-- T41 agreement acceptance with evidence).
--
-- Why: onboarding was manual (Excel menu -> photos by chat -> Google Drive -> Jack
-- checks names -> admin Menu import), and the old joinna.sariko.store form only made
-- a PDF on the seller's device: nothing ever reached SariKo.
--
-- Flow: POST /onboarding/applications inserts a 'draft' with a one-off upload_token
-- -> the form uploads documents + one photo per dish -> /submit flips it to
-- 'submitted' and clears the token. The admin app reviews and approves (creates the
-- seller + menu from `menu`).
--
-- Personal data (ID documents, bank account) -> private bucket, backend-only tables.
-- Dish photos move to the public bucket only when an admin approves.

create table if not exists public.onboarding_applications (
  id uuid not null default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  submitted_at timestamp with time zone,
  status text not null default 'draft',
  -- seller, as on the passport / CCCD
  first_name text not null,
  last_name text not null,
  date_of_birth date not null,
  nationality text not null,
  id_type text not null,                    -- passport | cccd
  id_number text not null,
  email text not null,
  phone text not null,                      -- E.164 (core/phone.to_e164_vn)
  residential_address text not null,        -- where the seller lives (T43), may differ from the kitchen
  tax_code text,
  tax_resident boolean,                     -- null = not sure; decides the PIT rate (Decree 117)
  -- store
  store_name text not null,
  store_description text,
  pickup_address text not null,             -- where the driver picks up
  maps_link text,                           -- Google Maps link of the kitchen; admin turns it into lat/lon
  opening_time time,
  closing_time time,
  menu jsonb not null,                      -- [{key, category, name, description, price, unit_label, preorder_day}]
  -- plan
  tier text not null,                       -- community | tindahan | negosyo | enterprise
  founding_invited boolean not null default false,
  -- payout (VN bank account in the seller's own name)
  bank_name text not null,
  bank_account_number text not null,
  bank_account_holder text not null,
  -- agreement evidence (T41)
  agreement_version text not null,          -- admin_settings.seller_agreement_version at signing, e.g. '20261016'
  agreed_at timestamp with time zone not null,
  signature_name text not null,             -- full name typed by the seller
  ip text,
  user_agent text,
  -- review
  upload_token text,                        -- cleared on submit
  admin_note text,
  reviewed_at timestamp with time zone,
  seller_profile_id uuid,                   -- set by the admin on approve (T43 reads through it); no FK
  constraint onboarding_applications_pkey primary key (id),
  constraint onboarding_applications_status_check check (status in ('draft','submitted','needs_info','approved','rejected')),
  constraint onboarding_applications_id_type_check check (id_type in ('passport','cccd')),
  constraint onboarding_applications_tier_check check (tier in ('community','tindahan','negosyo','enterprise'))
);
create index if not exists onboarding_applications_status_idx on public.onboarding_applications (status, submitted_at desc);

create table if not exists public.onboarding_files (
  id uuid not null default gen_random_uuid(),
  application_id uuid not null,
  kind text not null,                       -- id_document | residence_card | food_safety | business_registration | dish_photo
  item_key text,                            -- dish_photo: matches menu[].key
  storage_path text not null,
  content_type text not null,
  size_bytes integer not null,
  created_at timestamp with time zone not null default now(),
  constraint onboarding_files_pkey primary key (id),
  constraint onboarding_files_application_id_fkey foreign key (application_id) references public.onboarding_applications (id) on delete cascade,
  constraint onboarding_files_kind_check check (kind in ('id_document','residence_card','food_safety','business_registration','dish_photo')),
  constraint onboarding_files_item_key_check check ((kind = 'dish_photo') = (item_key is not null))
);
create index if not exists onboarding_files_application_idx on public.onboarding_files (application_id);

-- Backend-only (service_role bypasses RLS); no policies -> anon/authenticated get nothing.
alter table public.onboarding_applications enable row level security;
alter table public.onboarding_files enable row level security;

-- 10 MB = hard ceiling (nginx also caps a request at 10 MB); the real per-file
-- limit is admin_settings.onboarding_max_file_mb, checked by the backend.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values
  ('onboarding-files', 'onboarding-files', false, 10485760, array['image/jpeg','image/png','application/pdf'])
on conflict (id) do nothing;

-- Monthly fee in VND per plan (đề án II.4), shown on /join. First step of T49
-- (bill in VND instead of monthly_fee_usd); nothing bills from it yet and
-- monthly_fee_usd is left as is. founding = the fee after the free months.
alter table public.admin_tier_config add column if not exists monthly_fee_vnd numeric not null default 0;
comment on column public.admin_tier_config.monthly_fee_vnd is
  'Monthly fee in VND, excluding VAT. founding: fee after founding_free_months (admin_settings). Not billed yet (T49).';
update public.admin_tier_config t
   set monthly_fee_vnd = v.fee
  from (values ('community', 0), ('tindahan', 720000), ('negosyo', 1200000),
               ('enterprise', 2200000), ('founding', 720000), ('bodega', 0)) as v(tier, fee)
 where t.tier = v.tier;

-- Limits of the /join form, editable in the admin Settings page (integers > 0).
-- The backend reads them on every request and falls back to the same defaults
-- if a row is missing or invalid; the form gets them from GET /onboarding/settings.
-- Plan limits (dishes, categories per plan) stay in admin_tier_config.
insert into public.admin_settings (key, value, description) values
  ('onboarding_rate_limit_per_hour', '5'::jsonb,
   'Seller applications (/join) accepted per IP address per hour. Counted in memory per backend process.'),
  ('onboarding_upload_window_minutes', '180'::jsonb,
   'Minutes after a seller application is created during which its files can be uploaded and it can be submitted. After that the seller starts again.'),
  ('onboarding_max_file_mb', '5'::jsonb,
   'Max size in MB of one file in a seller application (ID, documents, dish photos). Must stay at 7 or below: nginx limits a request to 10 MB and base64 adds about a third.'),
  ('onboarding_max_files_per_kind', '2'::jsonb,
   'Max files per document type in a seller application (e.g. both sides of a CCCD).'),
  ('onboarding_max_dishes', '100'::jsonb,
   'Max dishes in a seller application, also for plans with unlimited dishes. Each dish needs one photo upload.'),
  ('onboarding_max_dish_price', '10000000'::jsonb,
   'Max price in VND of one dish in a seller application.'),
  ('onboarding_max_preorder_days', '14'::jsonb,
   'Max pre-order days of one dish in a seller application.'),
  ('onboarding_min_age', '18'::jsonb,
   'Minimum age in years to apply as a seller.'),
  ('onboarding_review_days', '2'::jsonb,
   'Working days SariKo promises to review a seller application in (text on the /join confirmation screen).'),
  ('seller_agreement_version', '20261016'::jsonb,
   'Current Seller Agreement version as a date number (YYYYMMDD). Applicants must sign this version. Change it only together with frontend/public/docs/sariko_seller_agreement.html.'),
  ('founding_slots', '50'::jsonb,
   'Number of Founding Seller places. Places left = this minus sellers on the founding plan (GET /sellers/founding/slots); also shown on /join.'),
  ('founding_free_months', '4'::jsonb,
   'Months without the monthly fee for a Founding Seller (text on /join; not billed yet, T49).')
on conflict (key) do nothing;
