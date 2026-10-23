-- ============================================================
-- One tax group for every seller: home-cooked food (docs/dev/tax-withholding/README.md, phase 2 H1-H2;
-- Jack 2026-10-23). The key stays 'goods_services' (VAT 3% + PIT 1.5% resident / 2% non-resident, set in
-- 20261021050000 and editable in admin Settings). The 'goods' / 'services' rates and the check
-- constraint stay: compute_order_withholding raises when a rate is missing, so nothing is dropped.
-- Orders already computed keep their wh_* snapshot (this only changes seller_profiles).
-- ============================================================

alter table public.seller_profiles alter column tax_category set default 'goods_services';

do $$
declare
  n integer;
begin
  update public.seller_profiles set tax_category = 'goods_services' where tax_category <> 'goods_services';
  get diagnostics n = row_count;
  raise notice 'seller_profiles moved to goods_services: % row(s)', n;
end $$;
