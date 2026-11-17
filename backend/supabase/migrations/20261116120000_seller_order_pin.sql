-- ============================================================
-- Seller order (flow 20261116-seller-order, QĐ-4, 5, 7, 12, 13, 14): the admin sets the order of the stores on the
-- buyer home page in bulk, and can pin a store so a re-sort keeps its place.
--   * seller_profiles.is_pinned: the admin's pin. display_order stays the only source of the order the buyer sees.
--   * display_order default 1000000: a store created from now on goes to the end of its group. Stores that exist
--     keep their number. (PROD's column is numeric, nullable and has no default, DEV's is integer not null default 0:
--     the default is the same statement on both.)
--   * admin_apply_seller_order(rows): sets display_order + is_pinned of the listed stores, all or none; an unknown or
--     repeated id is an error. Returns how many stores really changed. Only those two columns are written, so
--     on_seller_profiles_open (BEFORE UPDATE OF is_open) never fires.
--   * admin_seller_order_apply(rows, actor) / admin_seller_order_undo(actor): the same inside one lock, with the log
--     row in history_admin_actions ('seller_order_apply' params {before, after}, 'seller_order_undo' params
--     {undone_id, skipped}). Undo restores the "before" of the latest apply when nothing came after it; a store
--     deleted since is skipped. An apply that changes nothing writes no log row.
-- Expand-only: the marketplace backend reads seller_profiles by column names, the new column changes nothing for it.
-- Only the service role can call the functions (the admin backend).
-- ============================================================

alter table public.seller_profiles add column if not exists is_pinned boolean not null default false;
comment on column public.seller_profiles.is_pinned is
  'Admin pin (Seller order screen): a re-sort keeps a pinned store at its place in its group. Does not change what the buyer sees by itself, display_order does.';

alter table public.seller_profiles alter column display_order set default 1000000;


create or replace function public.admin_apply_seller_order(p_rows jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ids     uuid[];
  v_changed integer;
begin
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
    raise exception 'rows must be a json array';
  end if;
  select array_agg((e ->> 'id')::uuid) into v_ids from jsonb_array_elements(p_rows) e;
  if v_ids is null then
    return 0;
  end if;
  if array_position(v_ids, null) is not null or (select count(distinct x) from unnest(v_ids) x) <> cardinality(v_ids) then
    raise exception 'a seller id is missing or repeated';
  end if;
  -- lock in id order, so two calls at once wait for each other instead of deadlocking
  perform 1 from public.seller_profiles where id = any (v_ids) order by id for update;
  if (select count(*) from public.seller_profiles where id = any (v_ids)) <> cardinality(v_ids) then
    raise exception 'unknown seller id';
  end if;

  update public.seller_profiles s
     set display_order = r.display_order, is_pinned = r.is_pinned
    from (select (e ->> 'id')::uuid as id, (e ->> 'display_order')::integer as display_order,
                 (e ->> 'is_pinned')::boolean as is_pinned
            from jsonb_array_elements(p_rows) e) r
   where s.id = r.id
     and (s.display_order is distinct from r.display_order or s.is_pinned is distinct from r.is_pinned);
  get diagnostics v_changed = row_count;
  return v_changed;
end $$;


create or replace function public.admin_seller_order_apply(p_rows jsonb, p_actor text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_before  jsonb;
  v_after   jsonb;
  v_changed integer;
  v_log     bigint;
begin
  perform pg_advisory_xact_lock(hashtext('admin_seller_order'));   -- apply and undo one at a time

  -- display_order::integer: PROD's column is numeric, a "4.0" in the log could not be cast back
  select coalesce(jsonb_agg(jsonb_build_object('id', s.id, 'display_order', s.display_order::integer,
                                                'is_pinned', s.is_pinned) order by s.id), '[]'::jsonb)
    into v_before
    from public.seller_profiles s
   where s.id in (select (e ->> 'id')::uuid from jsonb_array_elements(p_rows) e);
  select coalesce(jsonb_agg(jsonb_build_object('id', e ->> 'id', 'display_order', (e ->> 'display_order')::integer,
                                                'is_pinned', (e ->> 'is_pinned')::boolean, 'group', e ->> 'group')), '[]'::jsonb)
    into v_after from jsonb_array_elements(p_rows) e;

  v_changed := public.admin_apply_seller_order(p_rows);
  if v_changed = 0 then
    return jsonb_build_object('changed', 0);
  end if;
  insert into public.history_admin_actions (action, actor, params, result)
  values ('seller_order_apply', p_actor, jsonb_build_object('before', v_before, 'after', v_after),
          jsonb_build_object('changed', v_changed))
  returning id into v_log;
  return jsonb_build_object('changed', v_changed, 'log_id', v_log);
end $$;


create or replace function public.admin_seller_order_undo(p_actor text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_last     record;
  v_rows     jsonb;
  v_total    integer;
  v_restored integer;
begin
  perform pg_advisory_xact_lock(hashtext('admin_seller_order'));

  select id, action, params into v_last
    from public.history_admin_actions
   where action in ('seller_order_apply', 'seller_order_undo')
   order by id desc limit 1;
  if v_last.id is null or v_last.action <> 'seller_order_apply' then
    return jsonb_build_object('status', 'nothing_to_undo');
  end if;

  v_total := jsonb_array_length(v_last.params -> 'before');
  select coalesce(jsonb_agg(b), '[]'::jsonb) into v_rows
    from jsonb_array_elements(v_last.params -> 'before') b
    join public.seller_profiles s on s.id = (b ->> 'id')::uuid;   -- a store deleted since is skipped
  perform public.admin_apply_seller_order(v_rows);
  v_restored := jsonb_array_length(v_rows);

  insert into public.history_admin_actions (action, actor, params, result)
  values ('seller_order_undo', p_actor, jsonb_build_object('undone_id', v_last.id, 'skipped', v_total - v_restored),
          jsonb_build_object('restored', v_restored));
  return jsonb_build_object('status', 'ok', 'restored', v_restored, 'skipped', v_total - v_restored,
                            'undone_id', v_last.id);
end $$;


revoke execute on function public.admin_apply_seller_order(jsonb) from public, anon, authenticated;
revoke execute on function public.admin_seller_order_apply(jsonb, text) from public, anon, authenticated;
revoke execute on function public.admin_seller_order_undo(text) from public, anon, authenticated;
grant execute on function public.admin_apply_seller_order(jsonb) to service_role;
grant execute on function public.admin_seller_order_apply(jsonb, text) to service_role;
grant execute on function public.admin_seller_order_undo(text) to service_role;
