-- INIT ADMIN ACCOUNT (run in the Supabase SQL editor)
-- verify_admin (core/auth.py) requires BOTH:
--   1. the email listed in the backend env ADMIN_EMAILS (comma-separated)
--   2. app_metadata.sariko_admin = true (only the service role / SQL editor can set it)
--
-- Creates the user (email confirmed, password set, sariko_admin flag) if missing;
-- if the email already exists, resets its password and sets the flag. Safe to re-run.
-- Edit v_email / v_password below. Change the password after the first login; do not commit a real one.
-- An existing admin must log out and back in, so the new JWT carries the flag.

DO $$
DECLARE
  v_email    text := lower('admin@sariko.store');
  v_password text := 'Sakriko@123';
  v_user_id  uuid;
BEGIN
  SELECT id INTO v_user_id FROM auth.users WHERE lower(email) = v_email;

  IF v_user_id IS NULL THEN
    v_user_id := gen_random_uuid();

    -- Token columns must be '' not NULL, or Supabase Auth fails to load the user on login
    INSERT INTO auth.users (
      instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
      confirmation_token, recovery_token, email_change_token_new, email_change
    ) VALUES (
      '00000000-0000-0000-0000-000000000000', v_user_id, 'authenticated', 'authenticated', v_email,
      extensions.crypt(v_password, extensions.gen_salt('bf')), now(),
      '{"provider": "email", "providers": ["email"], "sariko_admin": true}'::jsonb, '{}'::jsonb, now(), now(),
      '', '', '', ''
    );

    -- Email/password login needs a matching identity row
    INSERT INTO auth.identities (id, user_id, provider_id, provider, identity_data, last_sign_in_at, created_at, updated_at)
    VALUES (
      gen_random_uuid(), v_user_id, v_user_id::text, 'email',
      jsonb_build_object('sub', v_user_id::text, 'email', v_email, 'email_verified', true),
      now(), now(), now()
    );
  ELSE
    UPDATE auth.users
    SET encrypted_password = extensions.crypt(v_password, extensions.gen_salt('bf')),
        email_confirmed_at = coalesce(email_confirmed_at, now()),
        raw_app_meta_data  = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"sariko_admin": true}'::jsonb,
        updated_at         = now()
    WHERE id = v_user_id;
  END IF;
END $$;

-- Check: sariko_admin should be true
SELECT id, email, email_confirmed_at, raw_app_meta_data -> 'sariko_admin' AS sariko_admin
FROM auth.users
WHERE lower(email) = lower('admin@sariko.store');

-- Revoke admin:
-- UPDATE auth.users SET raw_app_meta_data = raw_app_meta_data - 'sariko_admin' WHERE lower(email) = lower('...');
