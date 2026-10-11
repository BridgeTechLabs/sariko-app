-- ============================================================
-- Web Push subscriptions — one row per browser/device that opted in.
-- endpoint is unique: the same device signing in as another user moves the
-- row over (upsert on endpoint) instead of pushing to both accounts.
-- Dead endpoints (push service answers 404/410) are deleted by the backend.
-- ============================================================

create table if not exists public.push_subscriptions (
  id uuid not null default gen_random_uuid (),
  user_id uuid not null,
  endpoint text not null,
  p256dh text not null,
  auth text not null,
  created_at timestamp with time zone not null default now(),
  constraint push_subscriptions_pkey primary key (id),
  constraint push_subscriptions_endpoint_key unique (endpoint),
  constraint push_subscriptions_user_id_fkey foreign key (user_id) references users (id) on delete cascade
);

create index if not exists push_subscriptions_user_id_idx on public.push_subscriptions (user_id);

-- Backend-only table (service_role bypasses RLS); no policies → anon/authenticated get nothing.
alter table public.push_subscriptions enable row level security;
