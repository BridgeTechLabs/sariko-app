-- ============================================================
-- Menu history (T31, đề án II.3 đ; Luật 122 Điều 17 / NĐ 248: posted goods
-- data must stay accessible ≥ 1 year from posting).
-- Every UPDATE or DELETE on menu_categories / food_items / food_item_variants
-- copies the OLD row here, whoever does it (marketplace backend, admin repo,
-- cascades from a deleted seller, SQL by hand) — so a deleted dish and every
-- earlier version of an edited one (name, description, price, image_url)
-- survive without changing any reader. Rows are never purged.
-- Expand-only: the running backend never reads this table.
-- ============================================================

create table if not exists public.menu_history (
  id bigint generated always as identity,
  table_name text not null,
  row_id uuid not null,
  op text not null,
  old_row jsonb not null,
  changed_at timestamp with time zone not null default now(),
  constraint menu_history_pkey primary key (id),
  constraint menu_history_op_check check (op in ('UPDATE', 'DELETE'))
);

create index if not exists menu_history_row_idx on public.menu_history (table_name, row_id);

-- Backend-only table (service_role bypasses RLS); no policies → anon/authenticated get nothing.
alter table public.menu_history enable row level security;

-- security definer: the history insert must not fail because the writer's role
-- has no policy on menu_history.
create or replace function public.log_menu_history()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- on_review_change rewrites food_items.rating_* on every review: not a seller edit, skip it.
  if tg_op = 'UPDATE'
     and (to_jsonb(old) - 'rating_avg' - 'rating_count') = (to_jsonb(new) - 'rating_avg' - 'rating_count') then
    return null;
  end if;
  insert into public.menu_history (table_name, row_id, op, old_row)
  values (tg_table_name, old.id, tg_op, to_jsonb(old));
  return null;
end;
$$;

drop trigger if exists menu_categories_history on public.menu_categories;
create trigger menu_categories_history after update or delete on public.menu_categories
  for each row execute function public.log_menu_history();

drop trigger if exists food_items_history on public.food_items;
create trigger food_items_history after update or delete on public.food_items
  for each row execute function public.log_menu_history();

drop trigger if exists food_item_variants_history on public.food_item_variants;
create trigger food_item_variants_history after update or delete on public.food_item_variants
  for each row execute function public.log_menu_history();
