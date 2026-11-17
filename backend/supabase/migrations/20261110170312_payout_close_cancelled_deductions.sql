-- ============================================================
-- T174 A1 (docs/dev/20261110-payout-fixes): a store is never charged for an order it was never paid for.
-- An admin who cancels a done order already in a payout can "Charge to seller": a deduction taken from a later payout,
-- since that payout would pay the order. When that payout is then cancelled or fails, the cancelled order goes back to
-- waiting but is never paid (only done orders are), so its deduction is closed in the same transaction:
--   * nothing taken by another payout -> the deduction row is deleted ('removed');
--   * already taken (in part or in full) by another payout -> it stops there: amount = what was taken ('stopped'); the
--     admin backend tells the team to pay that back by hand (rare).
-- Monthly fees (no order) and deductions of other orders are untouched. admin_cancel_payout and
-- admin_update_payout_status return the list as 'deductions_closed'. Their bodies are the 20261026000000 /
-- 20261016050000 ones, read on DEV on 2026-11-10 (same md5 as the migration files) plus the lines marked T174.
-- No table, index or constraint changes (read on DEV 2026-11-10: amount > 0 and applied_amount <= amount hold).
-- ============================================================

create or replace function public.admin_close_cancelled_order_deductions(p_payout_id uuid)
returns jsonb
language plpgsql
as $$
declare
  v_closed jsonb := '[]'::jsonb;
  v_d      record;
begin
  for v_d in
    select d.id, d.order_id, d.seller_id, d.amount,
           d.applied_amount - coalesce(a.amount, 0) as taken   -- taken by OTHER payouts
      from public.admin_payout_deductions d
      join public.orders o on o.id = d.order_id
      left join public.admin_payout_deduction_applications a on a.deduction_id = d.id and a.payout_id = p_payout_id
     where o.payout_id = p_payout_id
       and o.status = 'cancelled'
     for update of d
  loop
    delete from public.admin_payout_deduction_applications where deduction_id = v_d.id and payout_id = p_payout_id;
    if v_d.taken = 0 then
      delete from public.admin_payout_deductions where id = v_d.id;
    else
      update public.admin_payout_deductions set amount = v_d.taken, applied_amount = v_d.taken where id = v_d.id;
    end if;
    v_closed := v_closed || jsonb_build_object(
      'deduction_id', v_d.id, 'order_id', v_d.order_id, 'seller_id', v_d.seller_id, 'amount', v_d.amount,
      'taken', v_d.taken, 'action', case when v_d.taken = 0 then 'removed' else 'stopped' end);
  end loop;
  return v_closed;
end;
$$;

create or replace function public.admin_cancel_payout(p_payout_id uuid, p_cancelled_by text default null)
returns jsonb
language plpgsql
as $$
declare
  v_status  text;
  v_orders  int;
  v_payout  public.admin_payouts%rowtype;
  v_closed  jsonb;
begin
  select status into v_status from public.admin_payouts where id = p_payout_id for update;
  if not found then
    return jsonb_build_object('status', 'error', 'reason', 'not_found');
  end if;
  if v_status <> 'pending' then
    return jsonb_build_object('status', 'error', 'reason', 'not_pending', 'current', v_status);
  end if;

  v_closed := public.admin_close_cancelled_order_deductions(p_payout_id);   -- T174, while the orders still point here

  update public.orders
     set payout_status = 'pending',
         payout_id     = null
   where payout_id = p_payout_id;
  get diagnostics v_orders = row_count;

  update public.admin_payout_deductions d
     set applied_amount = d.applied_amount - a.amount
    from public.admin_payout_deduction_applications a
   where a.payout_id = p_payout_id
     and a.deduction_id = d.id;
  delete from public.admin_payout_deduction_applications where payout_id = p_payout_id;

  update public.admin_payouts
     set status = 'cancelled', cancelled_at = now(), cancelled_by = p_cancelled_by
   where id = p_payout_id
  returning * into v_payout;

  return jsonb_build_object('status', 'ok', 'payout', to_jsonb(v_payout), 'orders_returned', v_orders,
                            'deductions_closed', v_closed);   -- T174
end;
$$;

create or replace function public.admin_update_payout_status(
  p_payout_id uuid, p_new_status text, p_note text default null
) returns jsonb
language plpgsql
as $$
declare
  v_current_status text;
  v_paid_at        timestamptz;
  v_updated        public.admin_payouts%rowtype;
  v_closed         jsonb := '[]'::jsonb;   -- T174
begin
  -- Lock the payout row so concurrent status updates serialize.
  select status into v_current_status
  from public.admin_payouts
  where id = p_payout_id
  for update;

  if not found then
    return jsonb_build_object('status', 'error', 'reason', 'not_found');
  end if;

  -- Forward-only state machine.
  if not (
    (v_current_status = 'pending'    and p_new_status in ('processing', 'failed')) or
    (v_current_status = 'processing' and p_new_status in ('completed', 'failed'))
  ) then
    return jsonb_build_object(
      'status', 'error',
      'reason', 'invalid_transition',
      'detail', format('cannot transition from %s to %s', v_current_status, p_new_status)
    );
  end if;

  if p_new_status = 'completed' then
    v_paid_at := now();
  end if;

  update public.admin_payouts
     set status  = p_new_status,
         note    = coalesce(p_note, note),
         paid_at = coalesce(v_paid_at, paid_at)
   where id = p_payout_id
   returning * into v_updated;

  -- Side effect on orders, atomic with the payout update.
  if p_new_status = 'completed' then
    update public.orders
       set payout_status = 'paid_out'
     where payout_id = p_payout_id;
  elsif p_new_status = 'failed' then
    v_closed := public.admin_close_cancelled_order_deductions(p_payout_id);   -- T174, while the orders still point here

    update public.orders
       set payout_status = 'pending',
           payout_id     = null
     where payout_id = p_payout_id;

    -- T5: nothing was paid, so nothing was taken: reopen exactly this payout's
    -- share of each deduction (one application row per deduction per payout).
    update public.admin_payout_deductions d
       set applied_amount = d.applied_amount - a.amount
      from public.admin_payout_deduction_applications a
     where a.payout_id = p_payout_id
       and a.deduction_id = d.id;
    delete from public.admin_payout_deduction_applications
     where payout_id = p_payout_id;
  end if;

  return jsonb_build_object('status', 'ok', 'payout', to_jsonb(v_updated), 'deductions_closed', v_closed);   -- T174
end;
$$;

-- Only the admin backend (service_role) runs admin_* functions (Supabase grants new public functions to anon / authenticated).
revoke execute on function public.admin_close_cancelled_order_deductions(uuid) from public, anon, authenticated;
grant execute on function public.admin_close_cancelled_order_deductions(uuid) to service_role;
