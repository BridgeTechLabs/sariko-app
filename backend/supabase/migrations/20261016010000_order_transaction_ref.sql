-- ============================================================
-- Keep the VNPay transaction ref on the order. update_order_payment_status (called
-- by the IPN) only wrote it to payments, so orders.transaction_ref stayed NULL and
-- every refund (sariko-app create_refund_for_order, admin create_admin_refund) was
-- queued without original_txn_ref: the admin could not send any of them to VNPay.
-- ============================================================

create or replace function update_order_payment_status(
  p_order_id uuid,
  p_status text,
  p_transaction_ref text default null
) returns void as
$$
begin
  update public.orders
  set payment_status = p_status,
      paid_at = case when p_status = 'paid' then coalesce(paid_at, now()) else paid_at end,
      transaction_ref = coalesce(p_transaction_ref, transaction_ref)
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

-- Backfill paid orders from their successful payment, then the refunds already queued.
update public.orders o
   set transaction_ref = p.transaction_ref
  from public.payments p
 where p.order_id = o.id
   and p.status in ('succeeded', 'paid')
   and p.transaction_ref is not null
   and o.transaction_ref is null;

update public.refunds r
   set original_txn_ref = o.transaction_ref
  from public.orders o
 where o.id = r.order_id
   and r.original_txn_ref is null
   and o.transaction_ref is not null;
