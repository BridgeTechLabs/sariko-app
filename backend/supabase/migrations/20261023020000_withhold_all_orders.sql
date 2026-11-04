-- Seller tax is withheld on every paid order (Seller Agreement section 4; docs/dev/tax-withholding/README.md
-- phase 3 K1): a seller with yearly revenue of 500 million VND or less claims it back from the tax office.
-- annual_revenue_threshold 0 = compute_order_withholding taxes the whole food amount (the function is unchanged).
-- Only moves the shipped default (100000000); a value the admin already changed stays.
update public.admin_tax_config
   set rate = 0
 where key = 'annual_revenue_threshold'
   and rate = 100000000;

update public.admin_tax_config
   set description = 'Annual VND revenue per seller (calendar year, Vietnam time) above which tax is withheld; only the part above it is taxed. 0 = tax is withheld on every paid order (Seller Agreement section 4).'
 where key = 'annual_revenue_threshold';
