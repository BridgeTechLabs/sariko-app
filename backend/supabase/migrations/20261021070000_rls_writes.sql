-- ============================================================
-- Close direct writes through PostgREST with a user's JWT or the anon key (docs/dev/rls-writes/README.md).
-- Every write goes through the backends, which use the service role (secret key: bypasses RLS and grants).
-- Found on DEV + PROD (read-only, 2026-10-21):
--   * write policies on orders, seller_profiles, users, carts, cart_items, food_items, food_item_variants,
--     menu_categories, chat_conversations, chat_messages (+ PROD only: blog_posts), most with no column limit:
--     a seller could set payout_amount / payment_status on their orders or tier / commission_rate_override /
--     tax_* on their profile; a buyer could insert an order already 'paid'.
--   * anon + authenticated hold INSERT / UPDATE / DELETE / TRUNCATE on every public table (Supabase default).
--   * update_order_payment_status (SECURITY DEFINER, every overload) is executable by anon: anyone with the
--     public anon key could mark any order paid through /rest/v1/rpc.
--   * seller_profiles is readable in full by anon: bank account, phone, tax data, commission override.
-- Kept: every SELECT policy; chat_messages insert by a participant (the app sends chat messages from the
-- browser, stores/chat/chatStore.js) limited to the three columns it sends. Reading chat, orders, payments
-- and deliveries through RLS keeps working: those policies only need seller_profiles (id, user_id).
-- ============================================================

-- 1. Drop every write policy in public except the chat insert (also PROD-only drift such as blog_posts).
do $$
declare
  p record;
begin
  for p in
    select tablename, policyname from pg_policies
    where schemaname = 'public' and cmd <> 'SELECT'
      and not (tablename = 'chat_messages' and policyname = 'participant send message')
  loop
    execute format('drop policy %I on public.%I', p.policyname, p.tablename);
  end loop;
end $$;

-- 2. No table write grants for the client roles; chat_messages insert only for the columns the app sends.
revoke insert, update, delete, truncate on all tables in schema public from anon, authenticated;
grant insert (conversation_id, sender_id, body) on public.chat_messages to authenticated;

-- 3. seller_profiles: the client roles read only what the RLS policies of other tables look up.
--    A column added later is not readable by them unless a migration grants it.
revoke select on public.seller_profiles from anon, authenticated;
grant select (id, user_id) on public.seller_profiles to authenticated;

-- 4. update_order_payment_status: backend only (service role), every overload (PROD still has a 2-arg one).
do $$
declare
  f regprocedure;
begin
  for f in
    select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'update_order_payment_status'
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;

-- 5. Objects created by later migrations (role postgres) start closed too: no write grants on new tables,
--    no execute on new functions for the client roles (a function the browser must call is granted by name).
alter default privileges for role postgres in schema public
  revoke insert, update, delete, truncate on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated;
alter default privileges for role postgres
  revoke execute on functions from public;
