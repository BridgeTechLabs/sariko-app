def cart_item_unit_price(cart_item: dict) -> float:
    """Unit price of one cart row: the chosen variant's price, else the dish price.

    The order subtotal (apis/orders.py) and the order-item snapshot
    (dao/dao_order_items.py) must agree on this number, or orders.subtotal stops
    matching the sum of its own order_items. Defined once so the two cannot drift.

    Expects a cart_items row read by DAOCartItems.read_cart_items_by_user_id, whose
    `food_item_variants` embed is an object (or None) because cart_items.variant_id
    is a many-to-one FK — not a list like the menu-side embed.
    """
    variant = cart_item.get("food_item_variants")
    if variant:
        return variant["price"]
    return cart_item["food_items"]["price"]
