-- Founding tier = rate card (TODO T4): 17% commission from the first order, the
-- monthly fee (720.000 VND ≈ 29 USD, same as tindahan) waived for the first 4 months.
-- Prod had 0 / 0, so founding sellers paid no commission at all.
-- Applies to new orders only: each order snapshots its rate (orders.commission_rate).
-- The monthly fee is not billed anywhere yet (TODO T49); the 4 months will count
-- from seller_profiles.created_at until that work decides otherwise.
update public.admin_tier_config
   set commission_rate = 0.17,
       monthly_fee_usd = 29
 where tier = 'founding';
