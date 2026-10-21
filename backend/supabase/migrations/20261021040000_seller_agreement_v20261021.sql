-- Seller Agreement 2026-10-21: new monthly fees (Tindahan 750,000, Negosyo 1,250,000,
-- Enterprise 2,300,000, by invitation, up to 5 sellers), the Founding Seller plan as a
-- separate plan whose 17% service fee never changes (đề án v6 §25, §26, §28).
-- New applicants must sign this version; existing sellers are asked to sign it again
-- (seller profile completion). The 2026-10-18 text is kept at
-- frontend/public/docs/sariko_seller_agreement_20261018.html for those who signed it.
-- Only moves forward from 20261018, so re-running it (or an admin who already changed
-- the value) is a no-op.
update public.admin_settings
   set value = '20261021'::jsonb,
       updated_at = now()
 where key = 'seller_agreement_version'
   and value = '20261018'::jsonb;
