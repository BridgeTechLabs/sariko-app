-- Seller Agreement 2026-10-23: payouts are made every Tuesday for the orders completed Monday to
-- Sunday of the previous week (docs/dev/payout-cycle/README.md section 7). Existing sellers are
-- asked to sign it again (seller profile completion). The 2026-10-21 text is kept at
-- frontend/public/docs/sariko_seller_agreement_20261021.html for those who signed it.
-- Only moves forward from 20261021, so re-running it (or an admin who already changed
-- the value) is a no-op.
update public.admin_settings
   set value = '20261023'::jsonb,
       updated_at = now()
 where key = 'seller_agreement_version'
   and value = '20261021'::jsonb;
