-- Seed: platform-wide tax settings (no FK dependencies).
insert into public.admin_tax_config (key, rate, description)
values
  ('vat_rate',                   0.10,        'VAT on Sariko commission (platform service fee to sellers)'),
  ('withholding_rate_goods',     0.01,        'Withholding tax for goods sellers (imported products, dry goods)'),
  ('withholding_rate_services',  0.02,        'Withholding tax for service sellers (food, tutoring, tailoring)'),
  ('annual_revenue_threshold',   100000000,   'Annual VND threshold above which withholding tax applies')
on conflict (key) do nothing;
