-- ============================================================
-- Row Level Security — all policies, organized by table.
-- Clients (authenticated) read/write some tables directly via Supabase;
-- everything else goes through the backend (service_role, bypasses RLS).
-- Idempotent: every policy is dropped-if-exists before create.
--
-- NOTE: image uploads no longer use storage RLS — they go through backend
-- endpoints (service role). See archive/storage_policies.sql for the retired
-- storage.objects policies. Storage reads stay public via the bucket setting.
-- ============================================================

alter table public.users enable row level security;
alter table public.seller_profiles enable row level security;
alter table public.menu_categories enable row level security;
alter table public.food_items enable row level security;
alter table public.food_item_variants enable row level security;
alter table public.carts enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.reviews enable row level security;
alter table public.payments enable row level security;
alter table public.deliveries enable row level security;
alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

-- ── users ──────────────────────────────────────────────────────────────────
drop policy if exists "users can read own profile" on public.users;
create policy "users can read own profile"
on public.users for select
using (id = auth.uid());

drop policy if exists "users can update own profile" on public.users;
create policy "users can update own profile"
on public.users for update
using (id = auth.uid());

-- ── seller_profiles ────────────────────────────────────────────────────────
-- Public can browse storefronts; a seller edits only their own row.
-- NOTE: "public read" exposes every column (incl. user_id, phone) to anon.
-- Keep sensitive/column-shaped reads going through the backend.
drop policy if exists "seller read own profile" on public.seller_profiles;  -- superseded by public read
drop policy if exists "public read seller profiles" on public.seller_profiles;
create policy "public read seller profiles"
on public.seller_profiles for select
using (true);

drop policy if exists "seller update own profile" on public.seller_profiles;
create policy "seller update own profile"
on public.seller_profiles for update
using (user_id = auth.uid())
with check (user_id = auth.uid());

-- ── menu_categories ────────────────────────────────────────────────────────
drop policy if exists "public read categories" on public.menu_categories;
create policy "public read categories"
on public.menu_categories for select
using (true);

drop policy if exists "seller manage categories" on public.menu_categories;
create policy "seller manage categories"
on public.menu_categories for all
using (seller_id in (select id from public.seller_profiles where user_id = auth.uid()))
with check (seller_id in (select id from public.seller_profiles where user_id = auth.uid()));

-- ── food_items ─────────────────────────────────────────────────────────────
drop policy if exists "public read food" on public.food_items;
create policy "public read food"
on public.food_items for select
using (is_available = true);

drop policy if exists "seller manage food" on public.food_items;
create policy "seller manage food"
on public.food_items for all
using (seller_id in (select id from public.seller_profiles where user_id = auth.uid()))
with check (seller_id in (select id from public.seller_profiles where user_id = auth.uid()));

-- ── food_item_variants ─────────────────────────────────────────────────────
-- Mirrors food_items: a price level is no more sensitive than the dish price it
-- belongs to. Ownership is checked one hop up, through the parent dish.
drop policy if exists "public read variants" on public.food_item_variants;
create policy "public read variants"
on public.food_item_variants for select
using (is_available = true);

drop policy if exists "seller manage variants" on public.food_item_variants;
create policy "seller manage variants"
on public.food_item_variants for all
using (food_item_id in (
  select fi.id from public.food_items fi
  join public.seller_profiles sp on sp.id = fi.seller_id
  where sp.user_id = auth.uid()))
with check (food_item_id in (
  select fi.id from public.food_items fi
  join public.seller_profiles sp on sp.id = fi.seller_id
  where sp.user_id = auth.uid()));

-- ── carts / cart_items ─────────────────────────────────────────────────────
drop policy if exists "user manage own cart" on public.carts;
create policy "user manage own cart"
on public.carts for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "user manage own cart items" on public.cart_items;
create policy "user manage own cart items"
on public.cart_items for all
using (cart_id in (select id from public.carts where user_id = auth.uid()))
with check (cart_id in (select id from public.carts where user_id = auth.uid()));

-- ── orders / order_items ───────────────────────────────────────────────────
drop policy if exists "user read own orders" on public.orders;
create policy "user read own orders"
on public.orders for select
using (
    user_id = auth.uid()
    or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
);

drop policy if exists "user create order" on public.orders;
create policy "user create order"
on public.orders for insert
with check (user_id = auth.uid());

drop policy if exists "seller update order status" on public.orders;
create policy "seller update order status"
on public.orders for update
using (seller_id in (select id from public.seller_profiles where user_id = auth.uid()));

drop policy if exists "read order items of accessible orders" on public.order_items;
create policy "read order items of accessible orders"
on public.order_items for select
using (
    order_id in (
        select id from public.orders
        where user_id = auth.uid()
        or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
    )
);

-- ── reviews ────────────────────────────────────────────────────────────────
drop policy if exists "public read reviews" on public.reviews;
create policy "public read reviews"
on public.reviews for select
using (true);

drop policy if exists "user write own review" on public.reviews;
create policy "user write own review"
on public.reviews for insert
with check (user_id = auth.uid());

-- ── payments ───────────────────────────────────────────────────────────────
drop policy if exists "user read own payments" on public.payments;
create policy "user read own payments"
on public.payments for select
using (order_id in (select id from public.orders where user_id = auth.uid()));

-- ── deliveries ─────────────────────────────────────────────────────────────
drop policy if exists "read delivery of accessible orders" on public.deliveries;
create policy "read delivery of accessible orders"
on public.deliveries for select
using (
    order_id in (
        select id from public.orders
        where user_id = auth.uid()
        or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
    )
);

-- ── chat ───────────────────────────────────────────────────────────────────
-- RLS filters rows, but the authenticated role still needs table privileges.
-- Frontend reads history + sends messages directly; it reads chat_conversations
-- because the message policies reference it in a subquery. No anon access.
grant select on public.chat_conversations to authenticated;
grant select, insert on public.chat_messages to authenticated;
grant all on public.chat_conversations to service_role;
grant all on public.chat_messages to service_role;

-- Broadcast message inserts to subscribed participants (RLS still filters rows).
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'chat_messages'
  ) then
    alter publication supabase_realtime add table public.chat_messages;
  end if;
end $$;

drop policy if exists "participant read conversation" on public.chat_conversations;
create policy "participant read conversation"
on public.chat_conversations for select
using (
  buyer_id = auth.uid()
  or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
);

drop policy if exists "participant update conversation" on public.chat_conversations;
create policy "participant update conversation"
on public.chat_conversations for update
using (
  buyer_id = auth.uid()
  or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
);

drop policy if exists "participant read messages" on public.chat_messages;
create policy "participant read messages"
on public.chat_messages for select
using (
  conversation_id in (
    select id from public.chat_conversations
    where buyer_id = auth.uid()
       or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
  )
);

drop policy if exists "participant send message" on public.chat_messages;
create policy "participant send message"
on public.chat_messages for insert
with check (
  sender_id = auth.uid()
  and conversation_id in (
    select id from public.chat_conversations
    where buyer_id = auth.uid()
       or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
  )
);

drop policy if exists "recipient mark read" on public.chat_messages;
create policy "recipient mark read"
on public.chat_messages for update
using (
  conversation_id in (
    select id from public.chat_conversations
    where buyer_id = auth.uid()
       or seller_id in (select id from public.seller_profiles where user_id = auth.uid())
  )
);
