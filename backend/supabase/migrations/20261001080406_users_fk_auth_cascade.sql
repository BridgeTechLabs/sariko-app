-- Deleting an auth user left its public.users row behind (no FK), and the
-- orphan's email then blocked re-signup via users_email_key → 500 on /signup.
--
-- Users with orders/reviews/deliveries/chat_messages still cannot be deleted:
-- those FKs have no cascade, so the auth delete rolls back. Intended — that
-- history is accounting data.
--
-- Before pushing to prod, this must return no rows or the constraint fails:
--   select id, email from public.users u
--   where not exists (select 1 from auth.users a where a.id = u.id);

alter table public.users
  add constraint users_id_fkey
  foreign key (id) references auth.users (id) on delete cascade;
