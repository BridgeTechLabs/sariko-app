-- ============================================================
-- Option groups for dishes (seller-menu đợt 3, ADR 0003 option A).
-- A store's groups ("Drinks - choose 1") are shared by its dishes; an option is free or adds a whole-đồng
-- extra_price to the dish (or price-level) price. The cart row keeps the chosen option ids; the order row
-- keeps a snapshot (names + prices at order time) and price_snapshot stays "final price of one portion".
-- Expand-only: the running backend keeps working (option_ids defaults to empty, options_snapshot is null).
-- Read on DEV 13/11 before writing (README đợt 3): Postgres 17; cart_items unique = the two partial indexes
-- replaced below; food_items has no (id, seller_id) key yet.
-- ============================================================

-- The composite FKs below need it: a dish can only take groups of its own store (ADR D4).
alter table public.food_items add constraint food_items_id_seller_key unique (id, seller_id);

create table public.menu_option_groups (
  id uuid not null default gen_random_uuid(),
  seller_id uuid not null references public.seller_profiles (id) on delete cascade,
  name text not null,
  is_required boolean not null default false,
  max_select integer not null default 1 check (max_select >= 1),
  created_at timestamptz not null default now(),
  constraint menu_option_groups_pkey primary key (id),
  constraint menu_option_groups_id_seller_key unique (id, seller_id)
);
create index idx_menu_option_groups_seller on public.menu_option_groups (seller_id);

create table public.menu_options (
  id uuid not null default gen_random_uuid(),
  group_id uuid not null references public.menu_option_groups (id) on delete cascade,
  name text not null,
  extra_price numeric not null default 0,
  is_available boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  constraint menu_options_pkey primary key (id),
  -- also the index of the group_id lookups. Deferrable: checked at the end of the statement, not row by row, so
  -- one save may swap two names (Small <-> Large) in its single upsert (that upsert's arbiter is the primary key).
  constraint menu_options_group_name_key unique (group_id, name) deferrable initially immediate,
  constraint menu_options_extra_price_check check (extra_price >= 0 and extra_price = trunc(extra_price))
);

comment on column public.menu_options.extra_price is
  'Whole đồng added to the dish (or price level) price when the buyer picks this option; 0 = free.
   Read live by the cart (utils/pricing.py cart_item_unit_price); orders keep their own copy in
   order_items.options_snapshot, so a later change never alters a placed order.';

create table public.food_item_option_groups (
  -- not a key: the history trigger (log_history_menu) records old.id
  id uuid not null default gen_random_uuid(),
  food_item_id uuid not null,
  group_id uuid not null,
  seller_id uuid not null,
  sort_order integer not null default 0,
  constraint food_item_option_groups_pkey primary key (food_item_id, group_id),
  constraint food_item_option_groups_food_fkey foreign key (food_item_id, seller_id)
    references public.food_items (id, seller_id) on delete cascade,
  constraint food_item_option_groups_group_fkey foreign key (group_id, seller_id)
    references public.menu_option_groups (id, seller_id) on delete cascade
);
create index idx_food_item_option_groups_group on public.food_item_option_groups (group_id);

-- Backend only (service role): RLS on, no policy; no grants for the client roles.
alter table public.menu_option_groups enable row level security;
alter table public.menu_options enable row level security;
alter table public.food_item_option_groups enable row level security;
revoke all on public.menu_option_groups, public.menu_options, public.food_item_option_groups from anon, authenticated;

-- Posted goods data kept >= 1 year (20261016020000_history_menu.sql).
create trigger menu_option_groups_history after update or delete on public.menu_option_groups
  for each row execute function public.log_history_menu();
create trigger menu_options_history after update or delete on public.menu_options
  for each row execute function public.log_history_menu();
create trigger food_item_option_groups_history after update or delete on public.food_item_option_groups
  for each row execute function public.log_history_menu();

-- Cart: one row per (cart, dish, level, set of options). The ids are stored sorted and without repeats
-- (add_cart_item), so the same choice in another order is the same row.
alter table public.cart_items add column option_ids uuid[] not null default '{}';
create unique index cart_items_line_key on public.cart_items (cart_id, food_item_id, variant_id, option_ids)
  nulls not distinct;
drop index public.cart_items_dish_variant_key;
drop index public.cart_items_dish_novariant_key;

alter table public.order_items add column options_snapshot jsonb null
  constraint order_items_options_snapshot_check
  check (options_snapshot is null or jsonb_typeof(options_snapshot) = 'array');

comment on column public.order_items.options_snapshot is
  'The options picked at order time: [{"group", "option", "extra_price"}]. Display only: their prices are
   already inside price_snapshot. Null on rows without options and on orders placed before option groups.';

comment on column public.order_items.price_snapshot is
  'Final price of ONE portion at order time: the dish (or level) price plus the extra_price of every option
   picked (utils/pricing.py cart_item_unit_price). Every money reader multiplies it by quantity.';

-- Adds a cart row or adds to the same one, in one statement (two taps at once give one row). The cart row is
-- locked first, so two adds to different rows of the same cart cannot both pass the caps: the total of one
-- dish over all its rows <= p_max_qty and the number of rows <= p_max_lines (else exception quantity_max /
-- cart_max_lines, turned into a 400 by apis/cart.py). Option ids are sorted and de-duplicated here.
create function public.add_cart_item(p_cart_id uuid, p_food_item_id uuid, p_variant_id uuid, p_option_ids uuid[],
                                     p_qty integer, p_max_qty integer, p_max_lines integer)
returns void
language plpgsql set search_path = public as
$$
declare
  v_ids uuid[] := array(select distinct x from unnest(coalesce(p_option_ids, '{}')) x order by x);
begin
  perform 1 from carts where id = p_cart_id for update;
  if p_qty + coalesce((select sum(quantity) from cart_items
                        where cart_id = p_cart_id and food_item_id = p_food_item_id), 0) > p_max_qty then
    raise exception 'quantity_max';
  end if;
  if not exists (select 1 from cart_items where cart_id = p_cart_id and food_item_id = p_food_item_id
                    and variant_id is not distinct from p_variant_id and option_ids = v_ids)
     and (select count(*) from cart_items where cart_id = p_cart_id) >= p_max_lines then
    raise exception 'cart_max_lines';
  end if;
  insert into cart_items (cart_id, food_item_id, variant_id, option_ids, quantity)
  values (p_cart_id, p_food_item_id, p_variant_id, v_ids, p_qty)
  on conflict (cart_id, food_item_id, variant_id, option_ids)
  do update set quantity = cart_items.quantity + excluded.quantity;
end;
$$;
-- Functions in public are callable through /rest/v1/rpc with the anon key: only the backend may call this.
revoke execute on function public.add_cart_item(uuid, uuid, uuid, uuid[], integer, integer, integer)
  from public, anon, authenticated;
grant execute on function public.add_cart_item(uuid, uuid, uuid, uuid[], integer, integer, integer) to service_role;

-- Caps (BM4, QĐ3-10). Read with DAOAdminConfig.get_positive_int; a larger value is refused with a 400.
insert into public.admin_settings (key, value, description)
values
  ('cart_max_lines', '20'::jsonb,
   'Maximum number of different lines in one cart (a dish with other options is another line). A buyer adding one more line, or ordering a cart with more, is refused.'),
  ('menu_max_groups_per_dish', '10'::jsonb,
   'Maximum number of option groups one dish can use.'),
  ('menu_max_options_per_group', '30'::jsonb,
   'Maximum number of options in one option group.'),
  ('menu_max_groups_per_store', '50'::jsonb,
   'Maximum number of option groups one store can create.'),
  ('menu_option_max_extra_price', '1000000'::jsonb,
   'Highest extra price of one option, in đồng. Checked when the seller saves a price; options saved before a lower cap keep their price.')
on conflict (key) do nothing;

-- The cap now counts one dish over all its cart lines (other options or price levels), not one line.
update public.admin_settings
   set description = 'Maximum total portions of one dish across all cart lines (every price option and option choice together) in a cart or order (integer > 0). A larger total is refused when the buyer adds, changes or orders it.'
 where key = 'cart_max_quantity_per_item';
