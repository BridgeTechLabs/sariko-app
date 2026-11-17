-- T172 (docs/dev/20261110-refund-state): an order's refund state, worked out in one place.
-- The main refund is the one row whose reason is not duplicate_payment (refunds_order_id_key, a partial unique
-- index, allows one per order); duplicate_payment rows return a second payment and never decide it.
-- null = no main refund | in_progress = pending | failed = failed (the team can retry) | refunded = processed.
-- payment_status stays as it is (pending | paid | failed).
-- Callers: select "..., refund_state" on orders through PostgREST (a computed field), or refund_state(o) in SQL.
-- SECURITY INVOKER: refunds has RLS on and no policy, so only the backends' service role reads it.

create or replace function public.refund_state(o public.orders)
returns text
language sql
stable
security invoker
set search_path = ''
as $$
  select case r.status when 'pending' then 'in_progress' when 'failed' then 'failed' when 'processed' then 'refunded' end
  from public.refunds r
  where r.order_id = o.id and r.reason <> 'duplicate_payment'
$$;

revoke execute on function public.refund_state(public.orders) from public, anon, authenticated;
grant execute on function public.refund_state(public.orders) to service_role;

-- PostgREST must see the new field before the backend selects it (a select naming it fails with 400 until then)
notify pgrst, 'reload schema';
