-- ============================================================
-- Functions & triggers
-- The trigger that binds handle_user_create to auth.users is managed in the
-- Supabase dashboard (Auth hooks), not here.
-- ============================================================

-- ⚠️ WARNING: the two handle_user_create definitions below share the SAME name,
-- so the second CREATE OR REPLACE OVERWRITES the first — only the UPDATE body
-- survives. This looks like a latent bug (the INSERT-on-signup body is lost).
-- Preserved verbatim from the original functions.sql; review before relying on it.

-- Insert a public.users row after auth.users creates a record.
create or replace function public.handle_user_create()
returns trigger as
$$
begin
    if not exists (select 1 from public.users where id = new.id) then
        insert into public.users (
          id, email, name, is_seller, created_at, updated_at
        ) values (
            new.id,
            new.email,
            new.raw_user_meta_data->>'fullname',
            new.raw_user_meta_data->>'is_seller',
            new.created_at,
            new.updated_at
        );
    end if;
    return new;
end;
$$
language plpgsql security definer;

-- Sync avatar/phone from auth metadata (⚠️ overwrites the definition above).
create or replace function public.handle_user_create()
returns trigger as
$$
begin
    update public.users
    set
        avatar_url = new.raw_user_meta_data->>'avatar_url',
        phone = new.phone,
        updated_at = new.updated_at
    where id = new.id;
    return new;
end;
$$
language plpgsql security definer;


-- Update order + payment status together (used by the VNPay flow).
create or replace function update_order_payment_status(
  p_order_id uuid,
  p_status text,
  p_transaction_ref text default null
) returns void as
$$
begin
  update public.orders
  set payment_status = p_status
  where id = p_order_id;

  if p_transaction_ref is not null then
    update public.payments
    set status = p_status, transaction_ref = p_transaction_ref
    where order_id = p_order_id;
  end if;
end;
$$
language plpgsql security definer
set search_path = public;


-- Chat: on a new message, refresh the conversation preview / ordering columns
-- AND resurface the thread for anyone who had soft-deleted it (new activity un-hides).
-- SECURITY DEFINER so an authenticated message insert can update the parent
-- conversation without needing an UPDATE grant / RLS policy on that role.
create or replace function public.bump_chat_conversation () returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
begin
  update public.chat_conversations
     set last_message_at = new.created_at,
         last_message_text = new.body,
         buyer_deleted_at = null,
         seller_deleted_at = null
   where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists on_new_chat_message on public.chat_messages;
create trigger on_new_chat_message
  after insert on public.chat_messages
  for each row
  execute function public.bump_chat_conversation ();


-- Reviews: keep the denormalised rating columns in sync so every menu query can read
-- rating_avg / rating_count inline instead of aggregating per request.
-- A review row rolls up to exactly one place: per-dish rows (food_item_id not null) to
-- food_items, overall rows to seller_profiles. The averages are recomputed from scratch
-- rather than adjusted incrementally, so hand-deleting test rows self-heals.
-- The API only ever inserts; update/delete are covered for manual cleanup in the SQL editor.
create or replace function public.recalc_review_ratings () returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  v_food_item_id uuid;
  v_seller_id    uuid;
begin
  -- NEW is unassigned on DELETE, so pick the source row explicitly.
  if tg_op = 'DELETE' then
    v_food_item_id := old.food_item_id;
    v_seller_id    := old.seller_id;
  else
    v_food_item_id := new.food_item_id;
    v_seller_id    := new.seller_id;
  end if;

  if v_food_item_id is not null then
    update public.food_items f
       set rating_avg   = sub.avg_rating,
           rating_count = sub.cnt
      from (
        select round(avg(rating)::numeric, 1) as avg_rating,
               count(*)                       as cnt
          from public.reviews
         where food_item_id = v_food_item_id
      ) sub
     where f.id = v_food_item_id;

  elsif v_seller_id is not null then
    update public.seller_profiles s
       set rating_avg   = sub.avg_rating,
           rating_count = sub.cnt
      from (
        select round(avg(rating)::numeric, 1) as avg_rating,
               count(*)                       as cnt
          from public.reviews
         where seller_id = v_seller_id
           and food_item_id is null
      ) sub
     where s.id = v_seller_id;
  end if;

  return null;
end;
$$;

drop trigger if exists on_review_change on public.reviews;
create trigger on_review_change
  after insert or update or delete on public.reviews
  for each row
  execute function public.recalc_review_ratings ();


-- Orders: stamp updated_at on every write so the /head endpoints can answer
-- "did anything change?" from an index instead of refetching the whole list.
create or replace function public.set_orders_updated_at () returns trigger
  language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_orders_update on public.orders;
create trigger on_orders_update
  before update on public.orders
  for each row
  execute function public.set_orders_updated_at ();
