-- T181 logic + T182 (docs/dev/20261110-audit-rest): what the rest of the state audit needs from the database.

-- A28: an order nobody paid is cancelled this many minutes after its last pay link (services/payment_reconcile).
insert into public.admin_settings (key, value, description)
values ('unpaid_order_expire_minutes', '30'::jsonb,
        'Minutes after its last payment link (or its creation) after which an unpaid order is cancelled.')
on conflict (key) do nothing;

-- A33: a review can be hidden (by an admin, or by itself when its order is cancelled later): it leaves the store and
-- dish scores and every public read.
alter table public.review_stores add column if not exists is_hidden boolean not null default false;
alter table public.review_items add column if not exists is_hidden boolean not null default false;

drop policy if exists "public read review_stores" on public.review_stores;
create policy "public read review_stores" on public.review_stores for select using (not is_hidden);
drop policy if exists "public read review_items" on public.review_items;
create policy "public read review_items" on public.review_items for select using (not is_hidden);

create or replace function public.recalc_review_store_rating() returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  v_seller_id uuid := case when tg_op = 'DELETE' then old.seller_id else new.seller_id end;
begin
  update public.seller_profiles s
     set rating_avg = sub.avg_rating, rating_count = sub.cnt
    from (select round(avg(rating)::numeric, 1) as avg_rating, count(*) as cnt
            from public.review_stores where seller_id = v_seller_id and not is_hidden) sub
   where s.id = v_seller_id;
  return null;
end;
$$;

create or replace function public.recalc_review_item_rating() returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  v_food_item_id uuid;
begin
  foreach v_food_item_id in array array_remove(array[
      case when tg_op <> 'INSERT' then old.food_item_id end,
      case when tg_op <> 'DELETE' then new.food_item_id end], null)
  loop
    update public.food_items f
       set rating_avg = sub.avg_rating, rating_count = sub.cnt
      from (select round(avg(rating)::numeric, 1) as avg_rating, count(*) as cnt
              from public.review_items where food_item_id = v_food_item_id and not is_hidden) sub
     where f.id = v_food_item_id;
  end loop;
  return null;
end;
$$;

-- An order cancelled after it was reviewed (an admin cancel + refund of a done order): its reviews hide themselves.
create or replace function public.hide_reviews_of_cancelled_order() returns trigger
  language plpgsql
  security definer
  set search_path = public
as $$
begin
  update public.review_stores set is_hidden = true where order_id = new.id and not is_hidden;
  update public.review_items set is_hidden = true where order_id = new.id and not is_hidden;
  return null;
end;
$$;

drop trigger if exists hide_reviews_on_order_cancel on public.orders;
create trigger hide_reviews_on_order_cancel
  after update of status on public.orders
  for each row when (new.status = 'cancelled' and old.status is distinct from 'cancelled')
  execute function public.hide_reviews_of_cancelled_order();

revoke execute on function public.hide_reviews_of_cancelled_order() from public, anon, authenticated;

-- A35: the IPN's payment write touches only THIS payment's charge row; earlier attempts keep their own result and
-- reference. A successful charge reads 'succeeded', as the IPN writes it and the admin reports read it.
create or replace function public.update_order_payment_status(
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
       set status = case when p_status = 'paid' then 'succeeded' else p_status end
     where order_id = p_order_id and type = 'charge' and transaction_ref = p_transaction_ref;
  end if;
end;
$$
language plpgsql security definer
set search_path = public;

revoke execute on function public.update_order_payment_status(uuid, text, text) from public, anon, authenticated;

-- T182: an order holds its payout while ANY complaint on it is open. Resolving the complaint that holds it hands the
-- hold to another open complaint of the order, or releases it when none is left. The order row is locked first, so two
-- resolves of the same order run one after the other.
create or replace function public.set_complaint_status(
  p_complaint_id uuid, p_status text, p_resolution text default null
) returns jsonb
language plpgsql
as $$
declare
  v_complaint public.complaints%rowtype;
  v_other     public.complaints%rowtype;
begin
  perform 1 from public.orders where id = (select order_id from public.complaints where id = p_complaint_id) for update;
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
    select * into v_other from public.complaints
     where order_id = v_complaint.order_id and status <> 'resolved'
     order by created_at limit 1;
    if found then
      update public.orders
         set payout_hold_note = 'complaint ' || v_other.code
       where id = v_complaint.order_id and payout_hold
         and payout_hold_note = 'complaint ' || v_complaint.code;
      if found then
        update public.complaints set held_payout = true where id = v_other.id;
      end if;
    else
      update public.orders
         set payout_hold = false, payout_hold_note = null
       where id = v_complaint.order_id and payout_hold
         and payout_hold_note = 'complaint ' || v_complaint.code;
    end if;
  end if;

  return jsonb_build_object('status', 'ok', 'complaint', to_jsonb(v_complaint));
end;
$$;

revoke execute on function public.set_complaint_status(uuid, text, text) from public, anon, authenticated;

-- PostgREST must see the new columns before the backends select them
notify pgrst, 'reload schema';
