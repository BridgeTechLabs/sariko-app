"""sariko-app T181 A49 (docs/dev/20261110-audit-rest): GET /cart hands over the portions left of each dish with a daily
limit, so the cart can show a dish that has fewer left than the buyer put in. No DB."""
import apis.cart as cart_api


def test_a49_cart_dishes_carry_portions_left(monkeypatch):
    cart = {"cart_items": [{"quantity": 3, "food_items": {"id": "f1", "daily_portions": 5, "preorder_day": 0}},
                           {"quantity": 1, "food_items": {"id": "f2", "daily_portions": None, "preorder_day": 0}}]}
    monkeypatch.setattr(cart_api, "DAOCartItems", lambda: type("D", (), {"read_cart_items_by_user_id": lambda self, user_id: cart})())
    monkeypatch.setattr(cart_api.DAOFoodItems, "__init__", lambda self: None)
    monkeypatch.setattr(cart_api.DAOFoodItems, "read_portions_left", lambda self, ids, day: {"f1": 2})
    out = cart_api.get_current_cart({"id": "u1"})["cart"]
    assert out["cart_items"][0]["food_items"]["remaining_today"] == 2     # 3 in the cart, 2 left
    assert "remaining_today" not in out["cart_items"][1]["food_items"]     # no limit, nothing to show
