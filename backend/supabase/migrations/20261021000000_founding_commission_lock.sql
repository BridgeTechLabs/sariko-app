-- ============================================================
-- Founding plan keeps its commission for as long as a seller stays on it (đề án v6 §26, T99).
-- The lock is "never changes", not a value: the rate seeded/set at launch stays.
-- monthly_fee_vnd and the other columns of the founding row stay editable.
-- To end the offer, move sellers to another plan instead of changing this rate.
-- ============================================================

create or replace function public.lock_founding_commission()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'founding commission is locked'
    using hint = 'Founding sellers keep their commission rate for as long as they use the founding plan.';
end;
$$;

drop trigger if exists trg_lock_founding_commission on public.admin_tier_config;
create trigger trg_lock_founding_commission
  before update on public.admin_tier_config
  for each row
  when (old.tier = 'founding' and new.commission_rate is distinct from old.commission_rate)
  execute function public.lock_founding_commission();
