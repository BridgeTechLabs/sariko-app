-- T175 (docs/dev/20261110-refund-ops): what refund operations need from the database.

-- A6: the buyer's extra payments being returned (duplicate_payment refunds: a second payment of a paid order), as one
-- value on the order next to refund_state: {amount: whole VND of all of them, state: refunded when all processed,
-- in_progress otherwise (a failed one is retried)} or null. Read as a computed field ("..., duplicate_refund").
-- SECURITY INVOKER: refunds has RLS on and no policy, so only the backends' service role reads it.
create or replace function public.duplicate_refund(o public.orders)
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  select case when count(*) > 0 then jsonb_build_object(
           'amount', round(sum(r.amount))::bigint,
           'state', case when bool_and(r.status = 'processed') then 'refunded' else 'in_progress' end) end
  from public.refunds r
  where r.order_id = o.id and r.reason = 'duplicate_payment'
$$;

revoke execute on function public.duplicate_refund(public.orders) from public, anon, authenticated;
grant execute on function public.duplicate_refund(public.orders) to service_role;

-- A16: "ask VNPay again before anything else" as a flag the admin app sets, instead of matching note text.
-- Pending rows whose note the admin page matched until now keep their button.
alter table public.refunds add column if not exists needs_check boolean not null default false;
update public.refunds set needs_check = true where status = 'pending' and note ~ 'VNPay 94|querydr 0[67]';

-- A3: Process claims a pending row (sets processing_at) before it calls VNPay, and frees it after; "refunded by hand"
-- skips a row claimed in the last minutes, so a refund is never sent to VNPay and refunded by hand at once.
alter table public.refunds add column if not exists processing_at timestamptz;

insert into public.admin_settings (key, value, description)
values ('refund_stuck_hours', '24'::jsonb,
        'Hours after which a pending or failed refund counts as stuck on the admin Overview.')
on conflict (key) do nothing;

-- PostgREST must see the new field and column before the backends select them
notify pgrst, 'reload schema';
