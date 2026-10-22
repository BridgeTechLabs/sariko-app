-- ============================================================
-- T35: complaints in the app, tied to an order, with a tracking code and a status
-- (docs/dev/complaints/README.md; đề án II.2.4 d, II.3 h, III.1 c).
-- * complaints: one row per complaint. Backend only (service role): RLS on, no policy, no grant for
--   anon / authenticated. At most one unresolved complaint per (order, sender).
-- * code: "KN" + at least 6 digits from complaint_code_seq, set by create_complaint.
-- * create_complaint: insert + payout hold in one transaction. A buyer's complaint on an order whose
--   payout is still 'pending' (not in a payout yet) sets orders.payout_hold (note 'complaint <code>').
-- * set_complaint_status: forward only (received -> verifying -> resolved); resolving needs a
--   resolution and lifts the hold this complaint set (only if the order still carries its note, so a
--   hold an admin set by hand stays).
-- * 4 business parameters; private bucket "complaints" (photos, read through signed URLs).
-- * order_id ON DELETE CASCADE: admin_purge_orders (Danger Zone, test orders) deletes the order's
--   complaints with it. user_id has no FK: a complaint outlives the account.
-- ============================================================

-- 1. Parameters (admin Settings)
insert into public.admin_settings (key, value, description) values
  ('complaint_window_hours', '24'::jsonb,
   'Hours after an order ends (status_changed_at of done / cancelled / delivery_failed) during which the buyer or the seller can still file a complaint in the app. Open orders can always be complained about.'),
  ('complaint_max_images', '3'::jsonb,
   'Maximum number of photos per complaint.'),
  ('complaint_ack_hours', '24'::jsonb,
   'Hours within which a received complaint should be acknowledged (moved to verifying). Only flags it as late in the admin app.'),
  ('complaint_resolve_working_days', '7'::jsonb,
   'Working days (Monday-Friday) within which a complaint should be resolved. Only flags it as late in the admin app.')
on conflict (key) do nothing;

-- 2. Table
create sequence if not exists public.complaint_code_seq;

create table if not exists public.complaints (
  id uuid not null default gen_random_uuid(),
  code text not null,
  order_id uuid not null references public.orders (id) on delete cascade,
  user_id uuid not null,                          -- sender (buyer or the seller's user)
  sender_role text not null,
  channel text not null default 'app',
  category text not null,
  description text not null,
  image_paths text[] not null default '{}',       -- paths in the "complaints" bucket
  status text not null default 'received',
  resolution text,                                -- outcome, shown to the sender
  admin_note text,                                -- internal, never shown to users
  held_payout boolean not null default false,     -- this complaint set orders.payout_hold
  created_at timestamp with time zone not null default now(),
  acknowledged_at timestamp with time zone,       -- moved to verifying
  resolved_at timestamp with time zone,
  updated_at timestamp with time zone not null default now(),
  constraint complaints_pkey primary key (id),
  constraint complaints_code_key unique (code),
  constraint complaints_sender_role_check check (sender_role in ('buyer', 'seller')),
  constraint complaints_channel_check check (channel in ('app', 'email')),
  constraint complaints_status_check check (status in ('received', 'verifying', 'resolved')),
  constraint complaints_category_check check (
    (sender_role = 'buyer' and category in ('wrong_item', 'damaged', 'missing_item', 'late', 'other'))
    or (sender_role = 'seller' and category in ('buyer_issue', 'delivery_issue', 'payment_issue', 'other'))
  )
);
create unique index if not exists complaints_one_open_uidx
  on public.complaints (order_id, user_id) where status <> 'resolved';
create index if not exists complaints_user_idx on public.complaints (user_id, created_at desc);
create index if not exists complaints_status_idx on public.complaints (status, created_at desc);

alter table public.complaints enable row level security;
revoke all on public.complaints from anon, authenticated;
revoke all on sequence public.complaint_code_seq from anon, authenticated;

-- 3. Photos: private bucket, written and read by the backend only
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values
  ('complaints', 'complaints', false, 10485760, array['image/jpeg', 'image/png'])
on conflict (id) do nothing;

-- 4. Create (+ payout hold for a buyer's complaint)
create or replace function public.create_complaint(
  p_order_id uuid, p_user_id uuid, p_sender_role text, p_channel text, p_category text, p_description text
) returns jsonb
language plpgsql
as $$
declare
  v_n         bigint := nextval('public.complaint_code_seq');
  v_complaint public.complaints%rowtype;
begin
  insert into public.complaints (code, order_id, user_id, sender_role, channel, category, description)
  values ('KN' || lpad(v_n::text, greatest(6, length(v_n::text)), '0'),
          p_order_id, p_user_id, p_sender_role, p_channel, p_category, p_description)
  returning * into v_complaint;

  if p_sender_role = 'buyer' then
    update public.orders
       set payout_hold = true, payout_hold_note = 'complaint ' || v_complaint.code
     where id = p_order_id and payout_status = 'pending' and payout_hold = false;
    if found then
      update public.complaints set held_payout = true where id = v_complaint.id
      returning * into v_complaint;
    end if;
  end if;

  return to_jsonb(v_complaint);
end;
$$;

-- 5. Status (admin app)
create or replace function public.set_complaint_status(
  p_complaint_id uuid, p_status text, p_resolution text default null
) returns jsonb
language plpgsql
as $$
declare
  v_complaint public.complaints%rowtype;
begin
  select * into v_complaint from public.complaints where id = p_complaint_id for update;
  if not found then
    return jsonb_build_object('status', 'error', 'reason', 'not_found');
  end if;
  if not ((v_complaint.status = 'received' and p_status in ('verifying', 'resolved'))
          or (v_complaint.status = 'verifying' and p_status = 'resolved')) then
    return jsonb_build_object('status', 'error', 'reason', 'invalid_transition');
  end if;
  if p_status = 'resolved' and coalesce(btrim(p_resolution), '') = '' then
    return jsonb_build_object('status', 'error', 'reason', 'resolution_required');
  end if;

  update public.complaints
     set status          = p_status,
         acknowledged_at = coalesce(acknowledged_at, now()),
         resolved_at     = case when p_status = 'resolved' then now() end,
         resolution      = case when p_status = 'resolved' then btrim(p_resolution) else resolution end,
         updated_at      = now()
   where id = p_complaint_id
  returning * into v_complaint;

  if p_status = 'resolved' and v_complaint.held_payout then
    update public.orders
       set payout_hold = false, payout_hold_note = null
     where id = v_complaint.order_id and payout_hold
       and payout_hold_note = 'complaint ' || v_complaint.code;
  end if;

  return jsonb_build_object('status', 'ok', 'complaint', to_jsonb(v_complaint));
end;
$$;

revoke execute on function public.create_complaint(uuid, uuid, text, text, text, text) from public, anon, authenticated;
revoke execute on function public.set_complaint_status(uuid, text, text) from public, anon, authenticated;
grant execute on function public.create_complaint(uuid, uuid, text, text, text, text) to service_role;
grant execute on function public.set_complaint_status(uuid, text, text) to service_role;
