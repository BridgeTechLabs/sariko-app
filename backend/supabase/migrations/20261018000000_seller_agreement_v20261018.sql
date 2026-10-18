-- Seller Agreement 2026-10-18: payouts T+3 (was every 2 weeks), payouts held while a
-- buyer complaint is open, seller-fault refunds deducted from later payouts (đề án v6
-- II.4 c). New applicants must sign this version; the 2026-10-16 text is kept at
-- frontend/public/docs/sariko_seller_agreement_20261016.html for those who signed it.
-- Only moves forward from 20261016, so re-running it (or an admin who already changed
-- the value) is a no-op.
update public.admin_settings
   set value = '20261018'::jsonb,
       updated_at = now()
 where key = 'seller_agreement_version'
   and value = '20261016'::jsonb;
