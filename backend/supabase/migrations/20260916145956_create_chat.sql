-- ============================================================
-- Chat: buyer <-> seller messaging. One conversation per (buyer, seller) pair.
-- Named chat_* on purpose — Supabase ships realtime.messages already.
-- Pin / soft-delete are per participant (buyer_* and seller_* columns).
--
-- The bump trigger lives in functions/functions.sql; grants, realtime
-- publication, and RLS live in policies/rls.sql.
-- ============================================================

create table if not exists public.chat_conversations (
  id uuid not null default gen_random_uuid (),
  buyer_id uuid not null,
  seller_id uuid not null,
  last_message_at timestamp with time zone null,
  last_message_text text null,
  buyer_pinned_at timestamp with time zone null,
  seller_pinned_at timestamp with time zone null,
  buyer_deleted_at timestamp with time zone null,
  seller_deleted_at timestamp with time zone null,
  created_at timestamp with time zone not null default now(),
  constraint chat_conversations_pkey primary key (id),
  constraint chat_conversations_buyer_seller_key unique (buyer_id, seller_id),
  constraint chat_conversations_buyer_id_fkey foreign KEY (buyer_id) references users (id) on delete CASCADE,
  constraint chat_conversations_seller_id_fkey foreign KEY (seller_id) references seller_profiles (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_chat_conversations_buyer on public.chat_conversations using btree (buyer_id) TABLESPACE pg_default;
create index IF not exists idx_chat_conversations_seller on public.chat_conversations using btree (seller_id) TABLESPACE pg_default;


create table if not exists public.chat_messages (
  id uuid not null default gen_random_uuid (),
  conversation_id uuid not null,
  sender_id uuid not null,
  body text not null,
  created_at timestamp with time zone not null default now(),
  read_at timestamp with time zone null,
  constraint chat_messages_pkey primary key (id),
  constraint chat_messages_conversation_id_fkey foreign KEY (conversation_id) references chat_conversations (id) on delete CASCADE,
  constraint chat_messages_sender_id_fkey foreign KEY (sender_id) references users (id),
  constraint chat_messages_body_check check ((char_length(btrim(body)) > 0))
) TABLESPACE pg_default;

create index IF not exists idx_chat_messages_conversation on public.chat_messages using btree (conversation_id, created_at desc) TABLESPACE pg_default;
