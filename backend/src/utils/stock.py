"""Dish stock (seller-menu đợt 2, ADR 0004): food_items.stock = portions the dish can still sell, null = no limit.
Worked out on read, never stored as a flag (QĐ2-7)."""


def min_qty(food: dict) -> int:
    """The dish's minimum per order; null (old rows) counts as 1, as in SQL (QĐ2-12)."""
    return max(food.get("min_quantity") or 1, 1)


def stock_sold_out(food: dict) -> bool:
    """Fewer portions left than one order must take: buyers see it sold out (QĐ2-7)."""
    return food.get("stock") is not None and food["stock"] < min_qty(food)


def add_sold_out(items: list) -> list:
    """sold_out on each dish read with stock + min_quantity (QĐ2-12): read from the row, no RPC (was portions_left
    on every menu / cart read)."""
    for f in items:
        if f:
            f["sold_out"] = stock_sold_out(f)
    return items


def stock_error(wanted: dict, foods: dict):
    """The 409 detail for the first dish asked beyond its stock, wanted = {food_item_id: quantity over every cart row},
    foods = {food_item_id: dish row}. Only tells the buyer early: the stock is taken when the money comes in
    (reserve_order_stock, QĐ2-8). Code and text as the daily portions had them."""
    for food_id, qty in wanted.items():
        stock, name = foods[food_id].get("stock"), foods[food_id].get("name")
        if stock is not None and qty > stock:
            return {"code": "portions_left", "message": f"Only {stock} portion(s) left: {name}", "name": name, "remaining": stock}
    return None
