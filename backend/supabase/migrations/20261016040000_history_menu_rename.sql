-- ============================================================
-- DEV ran 20261016020000 while it still created `menu_history`; the file was
-- then edited to create `history_menu` (history_* prefix), which DEV will never
-- re-run. Rename DEV's table to match. No-op where 20261016020000 already
-- created history_menu (PROD).
-- The trigger function is recreated under its new name: the old function's
-- body inserts into menu_history and would fail every menu edit after the rename.
-- ============================================================

do $$
begin
  if to_regclass('public.menu_history') is not null and to_regclass('public.history_menu') is null then
    alter table public.menu_history rename to history_menu;
    alter table public.history_menu rename constraint menu_history_pkey to history_menu_pkey;
    alter table public.history_menu rename constraint menu_history_op_check to history_menu_op_check;
    alter index public.menu_history_row_idx rename to history_menu_row_idx;
  end if;
end;
$$;

-- Same body as 20261016020000.
create or replace function public.log_history_menu()
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
  insert into public.history_menu (table_name, row_id, op, old_row)
  values (tg_table_name, old.id, tg_op, to_jsonb(old));
  return null;
end;
$$;

drop trigger if exists menu_categories_history on public.menu_categories;
create trigger menu_categories_history after update or delete on public.menu_categories
  for each row execute function public.log_history_menu();

drop trigger if exists food_items_history on public.food_items;
create trigger food_items_history after update or delete on public.food_items
  for each row execute function public.log_history_menu();

drop trigger if exists food_item_variants_history on public.food_item_variants;
create trigger food_item_variants_history after update or delete on public.food_item_variants
  for each row execute function public.log_history_menu();

drop function if exists public.log_menu_history();
