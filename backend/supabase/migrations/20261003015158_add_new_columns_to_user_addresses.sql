-- Each address carries its own receiver, so an order can go to someone other
-- than the account holder.
--
-- Existing rows are backfilled from public.users before NOT NULL is applied;
-- users.name/phone are nullable, so missing values fall back to ''.

alter table public.user_addresses
  add column receiver_name text,
  add column phone_number text,
  add column note text,
  add column street_name text;

update public.user_addresses ua
set receiver_name = coalesce(u.name, ''),
    phone_number  = coalesce(u.phone, '')
from public.users u
where u.id = ua.user_id;

alter table public.user_addresses
  alter column receiver_name set not null,
  alter column phone_number set not null;

-- updated_at: added after the backfill so existing rows get now() once and
-- the trigger below doesn't need to exist yet.
alter table public.user_addresses
  add column updated_at timestamp with time zone not null default now();

create or replace function public.set_user_addresses_updated_at () returns trigger
  language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_user_addresses_update on public.user_addresses;
create trigger on_user_addresses_update
  before update on public.user_addresses
  for each row
  execute function public.set_user_addresses_updated_at ();
