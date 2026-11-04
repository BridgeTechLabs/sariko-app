from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def cart_item_unit_price(cart_item: dict) -> Decimal:
    """Unit price of one cart row: the chosen variant's price, else the dish price.

    The order subtotal (apis/orders.py) and the order-item snapshot
    (dao/dao_order_items.py) must agree on this number, or orders.subtotal stops
    matching the sum of its own order_items. Defined once so the two cannot drift.

    Expects a cart_items row read by DAOCartItems.read_cart_items_by_user_id, whose
    `food_item_variants` embed is an object (or None) because cart_items.variant_id
    is a many-to-one FK — not a list like the menu-side embed.
    """
    variant = cart_item.get("food_item_variants")
    price = variant["price"] if variant else cart_item["food_items"]["price"]
    return Decimal(str(price))


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
