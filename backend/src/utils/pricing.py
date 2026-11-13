from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

# PostgREST embed of a dish's option groups and their options (ADR 0003), on a food_items select.
OPTION_GROUPS_EMBED = ("food_item_option_groups(sort_order, menu_option_groups(id, name, is_required, max_select, "
                       "menu_options(id, name, extra_price, is_available, sort_order)))")


def dish_groups(food: dict) -> list:
    """The option groups of a dish read with OPTION_GROUPS_EMBED, in the dish's order, options in the group's
    order. The first call puts them on the dish as option_groups (the shape the apps read) in place of the embed."""
    if "option_groups" not in food:
        links = sorted(food.pop("food_item_option_groups", None) or [], key=lambda link: link["sort_order"])
        food["option_groups"] = [link["menu_option_groups"] for link in links if link.get("menu_option_groups")]
        for group in food["option_groups"]:
            group["menu_options"] = sorted(group.get("menu_options") or [], key=lambda o: o["sort_order"])
    return food["option_groups"]


def options_sold_out(food: dict) -> bool:
    """A required group with every option off: the dish can't be ordered (ADR 0003 point 8, computed on read)."""
    return any(g["is_required"] and not any(o["is_available"] for o in g["menu_options"]) for g in dish_groups(food))


def chosen_options(cart_item: dict) -> list:
    """[(group, option)] this cart row picked, in the dish's order. An id that is not an option of one of the
    dish's groups now (deleted, another store's, its group taken off the dish) is left out: apis/orders.py
    option_problem refuses the row."""
    ids = set(cart_item.get("option_ids") or [])
    return [(g, o) for g in dish_groups(cart_item["food_items"]) for o in g["menu_options"] if o["id"] in ids]


def options_snapshot(cart_item: dict):
    """order_items.options_snapshot of a cart row; None without options."""
    return [{"group": g["name"], "option": o["name"], "extra_price": o["extra_price"]}
            for g, o in chosen_options(cart_item)] or None


def cart_item_unit_price(cart_item: dict) -> Decimal:
    """Unit price of one cart row: the chosen variant's price, else the dish price, plus every chosen option's
    extra_price.

    The order subtotal (apis/orders.py), the order-item snapshot (dao/dao_order_items.py) and GET /cart must
    agree on this number, or orders.subtotal stops matching the sum of its own order_items. Defined once so
    they cannot drift.

    Expects a cart_items row read by DAOCartItems.read_cart_items_by_user_id, whose
    `food_item_variants` embed is an object (or None) because cart_items.variant_id
    is a many-to-one FK — not a list like the menu-side embed.
    """
    variant = cart_item.get("food_item_variants")
    price = variant["price"] if variant else cart_item["food_items"]["price"]
    return Decimal(str(price)) + sum((Decimal(str(o["extra_price"])) for _, o in chosen_options(cart_item)), Decimal(0))


def order_amounts(cart_items: list, commission_rate: Decimal, vat_rate: Decimal, delivery_fee=None) -> dict:
    """Money columns of a new order. VAT is on the commission, the payout excludes the
    delivery fee. Commission and VAT are rounded to 2 places (ROUND_HALF_UP), so
    payout + commission + VAT equals the subtotal exactly."""
    subtotal = sum((cart_item_unit_price(i) * i["quantity"] for i in cart_items), Decimal(0))
    commission_amount = (subtotal * commission_rate).quantize(CENT, ROUND_HALF_UP)
    vat_amount = (commission_amount * vat_rate).quantize(CENT, ROUND_HALF_UP)
    return {
        "subtotal": subtotal,
        "total_amount": subtotal + Decimal(str(delivery_fee or 0)),
        "commission_amount": commission_amount,
        "vat_amount": vat_amount,
        "payout_amount": subtotal - commission_amount - vat_amount,
    }
