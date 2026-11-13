import uuid

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

_GROUP_SELECT = ("id, name, is_required, max_select, "
                 "menu_options(id, name, extra_price, is_available, sort_order), food_item_option_groups(food_item_id)")


class OptionNameTaken(Exception):
    """menu_options_group_name_key: two options of one group with the same name."""


def _shape(group: dict) -> dict:
    """Options in their order; dish_ids = the dishes using the group (the seller's "used in N dishes")."""
    group["menu_options"] = sorted(group.get("menu_options") or [], key=lambda o: o["sort_order"])
    group["dish_ids"] = [link["food_item_id"] for link in group.pop("food_item_option_groups", None) or []]
    return group


class DAOMenuOptionGroups(DAOBase):
    """menu_option_groups + menu_options + food_item_option_groups (ADR 0003). Every call names the seller."""

    def read_store_groups(self, seller_id: str) -> list:
        rows = self._supabase_client.table("menu_option_groups").select(_GROUP_SELECT) \
            .eq("seller_id", seller_id).order("created_at").execute().data or []
        return [_shape(g) for g in rows]

    def read_group(self, group_id: str, seller_id: str):
        rows = self._supabase_client.table("menu_option_groups").select(_GROUP_SELECT) \
            .eq("id", group_id).eq("seller_id", seller_id).limit(1).execute().data
        return _shape(rows[0]) if rows else None

    def count_store_groups(self, seller_id: str) -> int:
        return self._supabase_client.table("menu_option_groups").select("id", count="exact") \
            .eq("seller_id", seller_id).limit(1).execute().count or 0

    def read_dish_links(self, food_item_id: str, seller_id: str) -> list:
        """[group_id] of a dish, in its order."""
        rows = self._supabase_client.table("food_item_option_groups").select("group_id") \
            .eq("food_item_id", food_item_id).eq("seller_id", seller_id).order("sort_order").execute().data or []
        return [r["group_id"] for r in rows]

    def save_group(self, seller_id: str, group_id, fields: dict, options: list) -> str:
        """Creates the group (group_id None) or updates it, then makes its options exactly `options` (dicts with
        name, extra_price, is_available and id for an existing one): the others are deleted, the list order is
        sort_order. The caller has checked that every given id is an option of this group."""
        table = self._supabase_client.table
        if group_id:
            table("menu_option_groups").update(fields).eq("id", group_id).eq("seller_id", seller_id).execute()
        else:
            group_id = table("menu_option_groups").insert(fields | {"seller_id": seller_id}).execute().data[0]["id"]
        rows = [{"id": o.get("id") or str(uuid.uuid4()), "group_id": group_id, "name": o["name"],
                 "extra_price": o["extra_price"], "is_available": o["is_available"], "sort_order": n}
                for n, o in enumerate(options)]
        # Deleted first, so a kept option may take a removed option's name; names swapped among the kept ones
        # pass because the unique name is checked at the end of the upsert (deferrable, migration)
        table("menu_options").delete().eq("group_id", group_id) \
            .not_.in_("id", [r["id"] for r in rows] or [str(uuid.uuid4())]).execute()
        try:
            if rows:
                table("menu_options").upsert(rows, on_conflict="id").execute()
        except PostgrestExceptionAPIError as e:
            if e.code == "23505":
                raise OptionNameTaken()
            raise
        return group_id

    def delete_group(self, group_id: str, seller_id: str):
        self._supabase_client.table("menu_option_groups").delete().eq("id", group_id).eq("seller_id", seller_id).execute()

    def attach(self, food_item_id: str, group_id: str, seller_id: str, sort_order: int):
        """A second attach of the same group to the same dish changes nothing (TC3-45)."""
        self._supabase_client.table("food_item_option_groups").upsert(
            {"food_item_id": food_item_id, "group_id": group_id, "seller_id": seller_id, "sort_order": sort_order},
            on_conflict="food_item_id,group_id", ignore_duplicates=True).execute()

    def detach(self, food_item_id: str, group_id: str, seller_id: str):
        self._supabase_client.table("food_item_option_groups").delete() \
            .eq("food_item_id", food_item_id).eq("group_id", group_id).eq("seller_id", seller_id).execute()

    def set_dish_order(self, food_item_id: str, seller_id: str, group_ids: list):
        for n, group_id in enumerate(group_ids):
            self._supabase_client.table("food_item_option_groups").update({"sort_order": n}) \
                .eq("food_item_id", food_item_id).eq("group_id", group_id).eq("seller_id", seller_id).execute()
