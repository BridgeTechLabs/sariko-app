"""Option groups (seller-menu đợt 3, ADR 0003): line price, order snapshot, the one option check of
/cart/add, GET /cart and /orders, the cart caps, and the seller routes. TC3-x of the flow README.
The database side (add_cart_item, constraints, FKs, grants, history) is tests/sql/g14_option_groups.sql.
No DB, no network.

Run from tests/backend:  pytest unit/test_option_groups.py
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apis import cart, orders, sellers
from dao.dao_menu_option_groups import OptionNameTaken
from dao.dao_order_items import DAOOrderItems
from utils.pricing import cart_item_unit_price, order_amounts, options_snapshot

SELLER, OTHER = "seller-1", "seller-2"
DISH = "00000000-0000-4000-8000-0000000000d1"
COCA, PEPSI, EGG, RICE, FOREIGN = ("00000000-0000-4000-8000-00000000000" + c for c in "12345")
LINE, LINE2 = "00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000a2"


def option(id_, name, extra_price, is_available=True, sort_order=0):
    return {"id": id_, "name": name, "extra_price": extra_price, "is_available": is_available, "sort_order": sort_order}


def group(id_, name, options, is_required=False, max_select=1, sort_order=0):
    """One food_item_option_groups row as OPTION_GROUPS_EMBED reads it."""
    return {"sort_order": sort_order, "menu_option_groups": {"id": id_, "name": name, "is_required": is_required,
                                                             "max_select": max_select, "menu_options": options}}


def combo(drinks_on=True, egg_on=True, max_extras=1, required=True):
    """Combo A 109.000: Drinks (choose 1, required) Coca / Pepsi 5.000; Extras (optional) Fried egg 5.000, Rice free."""
    return {"id": DISH, "seller_id": SELLER, "name": "Combo A", "price": 109000, "is_available": True,
            "preorder_day": 0, "daily_portions": None,
            "seller_profiles": {"status": "active", "lat": 10.77, "lon": 106.70, "is_open": True},
            "food_item_option_groups": [
                group("g-extras", "Extras", [option(EGG, "Fried egg", 5000, egg_on), option(RICE, "Rice", 0, sort_order=1)],
                      max_select=max_extras, sort_order=1),
                group("g-drinks", "Drinks", [option(COCA, "Coca-cola", 5000, drinks_on),
                                             option(PEPSI, "Pepsi", 5000, drinks_on, 1)], is_required=required),
            ]}


def line(option_ids, quantity=1, food=None, id_=LINE):
    return {"id": id_, "quantity": quantity, "option_ids": option_ids, "food_items": food or combo(),
            "food_item_variants": None}


# ── price (TC3-1, TC3-2, TC3-31) ─────────────────────────────────────────────

def test_tc3_1_line_price_adds_the_options():
    item = line([EGG, COCA], quantity=2)
    assert cart_item_unit_price(item) == Decimal("119000")
    assert cart_item_unit_price(item) * item["quantity"] == Decimal("238000")


def test_tc3_1_options_add_to_a_price_level_too():
    item = line([COCA]) | {"food_item_variants": {"price": 150000}}
    assert cart_item_unit_price(item) == Decimal("155000")


def test_tc3_2_money_same_as_a_plain_dish_of_the_same_price():
    plain = {"quantity": 2, "food_items": {"price": 119000}, "food_item_variants": None}
    rate, vat = Decimal("0.1"), Decimal("0.1")
    assert order_amounts([line([COCA, EGG], 2)], rate, vat) == order_amounts([plain], rate, vat)


def test_tc3_2_tc3_31_snapshot_in_the_dish_order_free_option_kept():
    assert options_snapshot(line([RICE, EGG, COCA])) == [
        {"group": "Drinks", "option": "Coca-cola", "extra_price": 5000},
        {"group": "Extras", "option": "Fried egg", "extra_price": 5000},
        {"group": "Extras", "option": "Rice", "extra_price": 0}]
    assert options_snapshot(line([COCA, RICE])) is not None
    plain = {"quantity": 1, "option_ids": [], "food_items": {"price": 50000}, "food_item_variants": None}
    assert options_snapshot(plain) is None and cart_item_unit_price(plain) == 50000


def _order_rows(cart_items):
    sent = []
    dao = DAOOrderItems.__new__(DAOOrderItems)
    query = SimpleNamespace(insert=lambda rows: sent.extend(rows) or query, execute=lambda: SimpleNamespace(data=sent))
    dao._supabase_client, dao._table_name = SimpleNamespace(table=lambda name: query), "order_items"
    dao.create_order_items_from_cart("order-1", cart_items)
    return sent


def test_tc3_2_tc3_3_tc3_35_order_rows_keep_their_own_copy():
    item = line([COCA], quantity=2)
    row = _order_rows([item])[0]
    assert (Decimal(row["price_snapshot"]), row["quantity"]) == (Decimal("114000"), 2)
    # the seller renames / reprices Coca afterwards: the row already sent keeps its words and price
    coca = item["food_items"]["option_groups"][0]["menu_options"][0]
    coca["name"], coca["extra_price"] = "Coke", 7000
    assert row["options_snapshot"] == [{"group": "Drinks", "option": "Coca-cola", "extra_price": 5000}]


# ── the one option check (TC3-6..10, TC3-17, TC3-32, TC3-33) ─────────────────

@pytest.mark.parametrize("food,ids,code", [
    (combo(), [COCA], None),
    (combo(), [COCA, RICE], None),
    (combo(), [FOREIGN], "option_unknown"),           # another store's option / a group not on the dish / deleted
    (combo(), [COCA, FOREIGN], "option_unknown"),
    (combo(drinks_on=False), [COCA], "options_sold_out"),   # TC3-17: the required group has nothing on
    (combo(egg_on=False), [COCA, EGG], "option_unavailable"),
    (combo(), [], "option_required"),                  # TC3-32: an old row, then the group became required
    (combo(), [EGG], "option_required"),
    (combo(), [COCA, PEPSI], "option_max"),            # TC3-33: more than the group allows
    (combo(max_extras=2), [COCA, EGG, RICE], None),
    (combo(max_extras=1), [COCA, EGG, RICE], "option_max"),   # TC3-33: max lowered to 1 after the row went in
    (combo(required=False), [], None),
])
def test_option_problem(food, ids, code):
    problem = orders.option_problem(line(ids, food=food))
    assert (problem or {}).get("code") == code
    if problem:
        assert problem["name"] == "Combo A" and problem["message"]


def test_problem_names_the_option_and_the_group():
    assert orders.option_problem(line([COCA, EGG], food=combo(egg_on=False)))["message"] == \
        "Fried egg is no longer available. Please choose again."
    assert orders.option_problem(line([EGG]))["message"] == "Choose an option in Drinks for Combo A"


# ── /cart (TC3-6..13, TC3-17, TC3-30, TC3-39, TC3-42, TC3-53, TC3-57) ──────────

@pytest.fixture
def cart_api(api, monkeypatch):
    """POST /cart/add + GET /cart + PATCH/DELETE with the dish combo() and the buyer's cart faked."""
    state = SimpleNamespace(food=combo(), added=[], lines=[], writes=[], cart_rows=[])

    class Items:
        def add_item(self, cart_id, food_item_id, variant_id, option_ids, quantity, max_quantity, max_lines):
            state.added.append((food_item_id, option_ids, quantity))

        def read_cart_items_by_user_id(self, user_id):
            return {"id": "cart", "seller_id": SELLER, "cart_items": state.cart_rows}

        def read_lines(self, cart_id):
            return state.lines

        def update_quantity(self, cart_id, item_id, quantity):
            state.writes.append(("update", item_id, quantity))
            return [{"id": item_id}]

        def remove_item(self, cart_id, item_id):
            state.writes.append(("remove", item_id))
            return [{"id": item_id}]

    monkeypatch.setattr(cart, "_validate_variant", lambda *a: None)
    monkeypatch.setattr(cart, "DAOFoodItems", lambda: SimpleNamespace(read_order_gate=lambda i: state.food,
                                                                        add_remaining_today=lambda items: items))
    monkeypatch.setattr(cart, "DAOCarts", lambda: SimpleNamespace(
        read_cart_by_user_id_seller_id=lambda user_id: {"id": "cart", "seller_id": SELLER}))
    monkeypatch.setattr(cart, "DAOCartItems", Items)
    monkeypatch.setattr(orders, "DAOAdminConfig", lambda: SimpleNamespace(get_positive_int=lambda key, default: default))
    state.client = api(cart.router)
    return state


def _add(state, option_ids, **extra):
    return state.client.post("/cart/add", json={"seller_id": SELLER, "food_item_id": DISH, "quantity": 1,
                                                "option_ids": option_ids, **extra})


def test_add_with_options_sorted_without_repeats(cart_api):   # TC3-36 (the database sorts too), TC3-11
    assert _add(cart_api, [EGG, COCA, EGG], price=1, unit_price=1).status_code == 200
    assert cart_api.added == [(DISH, sorted([COCA, EGG]), 1)]


@pytest.mark.parametrize("ids,status,code", [
    ([FOREIGN], 400, "option_unknown"),     # TC3-6, TC3-7, TC3-8 (deleted)
    ([COCA, PEPSI], 400, "option_max"),     # TC3-10
    ([], 400, "option_required"),           # TC3-10, TC3-39: the quick "+" without the sheet
])
def test_add_refuses_bad_options(cart_api, ids, status, code):
    res = _add(cart_api, ids)
    assert (res.status_code, res.json()["detail"]["code"]) == (status, code) and cart_api.added == []


def test_tc3_8_tc3_17_off_option_and_sold_out_dish(cart_api):
    cart_api.food = combo(egg_on=False)
    assert _add(cart_api, [COCA, EGG]).json()["detail"]["code"] == "option_unavailable"
    cart_api.food = combo(drinks_on=False)
    res = _add(cart_api, [])
    assert (res.status_code, res.json()["detail"]["code"]) == (409, "options_sold_out") and cart_api.added == []


@pytest.mark.parametrize("ids", [["not-a-uuid"], [COCA] * 31, "abc"])
def test_tc3_12_tc3_57_option_ids_shape_is_422(cart_api, ids):
    assert _add(cart_api, ids).status_code == 422 and cart_api.added == []


def test_tc3_53_dish_of_another_store_is_400(cart_api):
    cart_api.food = combo() | {"seller_id": OTHER}
    res = _add(cart_api, [COCA])
    assert res.status_code == 400 and cart_api.added == []


def test_tc3_30_tc3_32_get_cart_prices_each_row_and_flags_the_bad_one(cart_api):
    cart_api.cart_rows = [line([COCA, EGG], 2), line([], 1, id_=LINE2)]
    rows = cart_api.client.get("/cart").json()["cart"]["cart_items"]
    assert rows[0]["unit_price"] == 119000 and rows[0]["problem"] is None
    assert rows[0]["options"] == [{"group": "Drinks", "option": "Coca-cola", "extra_price": 5000},
                                  {"group": "Extras", "option": "Fried egg", "extra_price": 5000}]
    assert rows[1]["unit_price"] == 109000 and rows[1]["problem"]["code"] == "option_required"
    assert [g["name"] for g in rows[0]["food_items"]["option_groups"]] == ["Drinks", "Extras"]   # to choose again


def test_tc3_42_tc3_13_rows_of_another_cart_are_404(cart_api):
    cart_api.lines = [{"id": LINE, "food_item_id": DISH, "variant_id": None, "option_ids": [COCA], "quantity": 1}]
    c = cart_api.client
    assert c.patch("/cart/update", json={"id": LINE2, "quantity": 2}).status_code == 404   # not in the caller's cart
    assert c.delete(f"/cart/remove/{LINE2}").status_code == 404
    assert c.patch("/cart/update", json={"id": "x", "quantity": 2}).status_code == 422
    assert c.patch("/cart/update", json={"quantity": 2}).status_code == 404   # no row named
    assert c.delete("/cart/remove/x").status_code == 422
    assert cart_api.writes == []


def test_tc3_63_old_way_never_touches_a_row_with_options(cart_api):
    cart_api.lines = [{"id": LINE, "food_item_id": DISH, "variant_id": None, "option_ids": [COCA], "quantity": 1}]
    assert cart_api.client.delete(f"/cart/remove/{DISH}").status_code == 404
    assert cart_api.client.patch("/cart/update", json={"food_item_id": DISH, "quantity": 2}).status_code == 404
    assert cart_api.writes == []


def test_tc3_43_patch_cannot_change_the_options(cart_api):
    cart_api.lines = [{"id": LINE, "food_item_id": DISH, "variant_id": None, "option_ids": [COCA], "quantity": 1}]
    assert cart_api.client.patch("/cart/update", json={"id": LINE, "quantity": 2, "option_ids": [PEPSI]}).status_code == 200
    assert cart_api.writes == [("update", LINE, 2)]


# ── POST /orders (TC3-18, TC3-29, TC3-52, TC3-53, TC3-62, TC3-64) ─────────────

@pytest.fixture
def place(monkeypatch):
    """POST /orders (pickup, same day) of state.rows; state.items = what create_order_items_from_cart got."""
    state = SimpleNamespace(rows=[], reads=0, created=[], items=None)

    def read_cart(user_id):
        state.reads += 1
        return {"id": "cart", "seller_id": SELLER, "cart_items": state.rows}

    monkeypatch.setattr(orders, "DAOCartItems", lambda: SimpleNamespace(read_cart_items_by_user_id=read_cart))
    monkeypatch.setattr(orders, "DAOOrders", lambda: SimpleNamespace(
        read_orders_by_user_id=lambda user_id: [],
        create_order=lambda **kw: state.created.append(kw) or {"id": "order", **kw}))
    monkeypatch.setattr(orders, "DAOSellerProfiles", lambda: SimpleNamespace(read_seller_order_info=lambda s: {
        "user_id": "seller-user", "is_open": True, "commission_rate": Decimal("0.1")}))
    monkeypatch.setattr(orders, "DAOAdminConfig", lambda: SimpleNamespace(
        get_tax_rate=lambda key: Decimal("0.1"), get_positive_int=lambda key, default: default))
    monkeypatch.setattr(orders, "DAOOrderItems", lambda: SimpleNamespace(
        create_order_items_from_cart=lambda order_id, cart_items: setattr(state, "items", cart_items)))
    monkeypatch.setattr(orders, "DAOCarts", lambda: SimpleNamespace(delete_cart=lambda cart_id: None))

    def call():
        try:
            return orders.create_order(orders.Schema.RequestCreateOrder(delivery_method="pickup"), user={"id": "buyer"})
        except orders.HTTPException as e:
            return e
    state.call = call
    return state


def test_tc3_29_subtotal_is_the_sum_of_its_own_rows_from_one_read(place):
    place.rows = [line([COCA], 1), line([PEPSI, EGG], 2, id_=LINE2)]
    assert place.call()["success"]
    order = place.created[0]
    assert order["subtotal"] == Decimal("114000") + 2 * Decimal("119000")
    rows = _order_rows(place.items)
    assert sum(Decimal(r["price_snapshot"]) * r["quantity"] for r in rows) == order["subtotal"]
    assert place.reads == 1 and place.items is place.rows   # priced, checked and copied from the same read


def test_tc3_18_off_option_names_it_and_the_row(place):
    place.rows = [line([COCA], 1), line([COCA, EGG], 1, food=combo(egg_on=False), id_=LINE2)]
    e = place.call()
    assert e.status_code == 400 and place.created == []
    assert e.detail == {"code": "option_unavailable", "message": "Fried egg is no longer available. Please choose again.",
                        "name": "Combo A", "option": "Fried egg", "cart_item_id": LINE2}


def test_tc3_52_tc3_62_tc3_65_dish_total_over_all_rows(place):
    place.rows = [line([COCA], 30), line([PEPSI], 30, id_=LINE2)]   # 30 + 30 > 50
    e = place.call()
    assert (e.status_code, e.detail["code"]) == (400, "quantity_max") and place.created == []


def test_tc3_64_too_many_rows(place):
    place.rows = [line([COCA], 1, id_=f"row-{n}") for n in range(21)]
    e = place.call()
    assert (e.status_code, e.detail["code"]) == (400, "cart_max_lines") and place.created == []


def test_tc3_53_dish_of_another_store_in_the_cart(place):
    place.rows = [line([COCA], 1, food=combo() | {"seller_id": OTHER})]
    e = place.call()
    assert e.status_code == 400 and place.created == []


# ── seller routes (TC3-20, TC3-44..46, TC3-54, TC3-55, TC3-66, TC3-67, TC3-69) ──

@pytest.fixture
def seller_api(api, monkeypatch):
    """Store SELLER owns dish DISH and group G (Coca 5.000); the other store owns group B and dish D2."""
    g, b, d2 = "00000000-0000-4000-8000-0000000000e1", "00000000-0000-4000-8000-0000000000e2", "00000000-0000-4000-8000-0000000000d2"
    state = SimpleNamespace(g=g, b=b, d2=d2, saved=[], attached=[], detached=[], deleted=[], links=[], ordered=[], count=0,
                            limits=dict(sellers.MENU_LIMITS), taken=False)
    groups = {(g, SELLER): {"id": g, "name": "Drinks", "is_required": True, "max_select": 1, "dish_ids": [DISH],
                            "menu_options": [option(COCA, "Coca-cola", 5000)]},
              (b, OTHER): {"id": b, "name": "B", "is_required": False, "max_select": 1, "dish_ids": [],
                           "menu_options": [option(FOREIGN, "x", 0)]}}
    dishes = {(DISH, SELLER), (d2, OTHER)}

    class Groups:
        def read_group(self, group_id, seller_id):
            found = groups.get((group_id, seller_id))
            return dict(found) if found else None

        def count_store_groups(self, seller_id):
            return state.count

        def read_dish_links(self, food_item_id, seller_id):
            return list(state.links)

        def save_group(self, seller_id, group_id, fields, options):
            if state.taken:
                raise OptionNameTaken()
            state.saved.append((group_id, fields, options))
            return group_id or g

        def attach(self, *a):
            state.attached.append(a)

        def detach(self, *a):
            state.detached.append(a)
            state.links = [x for x in state.links if x != a[1]]

        def set_dish_order(self, food_item_id, seller_id, group_ids):
            state.ordered.append(group_ids)

        def delete_group(self, *a):
            state.deleted.append(a)

    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: SELLER)
    monkeypatch.setattr(sellers, "DAOMenuOptionGroups", Groups)
    monkeypatch.setattr(sellers, "DAOFoodItems", lambda: SimpleNamespace(
        read_owned_by_seller=lambda item_id, seller_id: {"id": item_id} if (item_id, seller_id) in dishes else None))
    monkeypatch.setattr(sellers, "_menu_limits", lambda: state.limits)
    state.client = api(sellers.router)
    return state


def body(**kw):
    return {"name": "Drinks", "is_required": True, "max_select": 1,
            "options": [{"name": "Coca-cola", "extra_price": 5000}, {"name": "Water"}]} | kw


def test_create_from_a_dish_and_put_on_it(seller_api):
    seller_api.links = ["other-group"]
    res = seller_api.client.post(f"/sellers/me/menu/items/{DISH}/option-groups", json=body())
    assert res.status_code == 200 and res.json()["group"]["dish_ids"] == [DISH]
    (group_id, fields, options), = seller_api.saved
    assert group_id is None and fields == {"name": "Drinks", "is_required": True, "max_select": 1}
    assert options == [{"id": None, "name": "Coca-cola", "extra_price": 5000, "is_available": True},
                       {"id": None, "name": "Water", "extra_price": 0, "is_available": True}]
    assert seller_api.attached == [(DISH, seller_api.g, SELLER, 1)]   # after the dish's other group


def test_create_with_an_existing_option_id_is_404(seller_api):   # someone's option id on a new group
    res = seller_api.client.post(f"/sellers/me/menu/items/{DISH}/option-groups",
                                 json=body(options=[{"id": FOREIGN, "name": "x"}]))
    assert res.status_code == 404 and seller_api.saved == []


def test_tc3_54_another_store_gets_404_everywhere(seller_api):
    s, c = seller_api, seller_api.client
    calls = [c.post(f"/sellers/me/menu/items/{s.d2}/option-groups", json=body()),
             c.put(f"/sellers/me/menu/option-groups/{s.b}", json=body()),
             c.delete(f"/sellers/me/menu/option-groups/{s.b}"),
             c.post(f"/sellers/me/menu/items/{DISH}/option-groups/{s.b}"),     # TC3-14: B's group on my dish
             c.post(f"/sellers/me/menu/items/{s.d2}/option-groups/{s.g}"),
             c.delete(f"/sellers/me/menu/items/{DISH}/option-groups/{s.b}"),
             c.put(f"/sellers/me/menu/items/{s.d2}/option-groups", json={"group_ids": []}),
             c.put(f"/sellers/me/menu/option-groups/{s.g}", json=body(options=[{"id": FOREIGN, "name": "x"}]))]
    assert [(r.status_code, r.json()) for r in calls] == [(404, {"detail": "Not found"})] * len(calls)
    assert s.saved == s.attached == s.detached == s.deleted == []


def test_tc3_20_group_in_use_is_not_deleted(seller_api):
    res = seller_api.client.delete(f"/sellers/me/menu/option-groups/{seller_api.g}")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "group_in_use" and seller_api.deleted == []


def test_tc3_44_same_name_twice_is_409(seller_api):
    url = f"/sellers/me/menu/option-groups/{seller_api.g}"
    res = seller_api.client.put(url, json=body(options=[{"name": "Coke"}, {"name": "Coke "}]))
    assert res.status_code == 409 and seller_api.saved == []
    seller_api.taken = True   # the database's unique (group_id, name)
    assert seller_api.client.put(url, json=body()).status_code == 409


def test_tc3_45_attach_twice_writes_once(seller_api):
    seller_api.links = [seller_api.g]
    assert seller_api.client.post(f"/sellers/me/menu/items/{DISH}/option-groups/{seller_api.g}").status_code == 200
    assert seller_api.attached == []


@pytest.mark.parametrize("bad", [{"max_select": 0}, {"max_select": -1}, {"max_select": "abc"}, {"options": []},
                                 {"options": [{"name": "x", "extra_price": -1}]},
                                 {"options": [{"name": "x", "extra_price": 1.5}]},
                                 {"options": [{"name": "x", "extra_price": "abc"}]},
                                 {"name": "x" * 61}, {"name": "  "}])
def test_tc3_46_tc3_55_bad_input_is_422(seller_api, bad):
    assert seller_api.client.put(f"/sellers/me/menu/option-groups/{seller_api.g}", json=body(**bad)).status_code == 422
    assert seller_api.saved == []


def test_tc3_69_names_count_characters():
    from schemas.request_option_group import RequestOption
    name = "Nước mía 🍹" + "ạ" * 50
    assert len(name) == 60 and RequestOption(name=name).name == name
    with pytest.raises(Exception):
        RequestOption(name=name + "ạ")


def test_tc3_55_tc3_66_caps_at_the_value_pass_one_more_is_400(seller_api):
    s, c = seller_api, seller_api.client
    create = f"/sellers/me/menu/items/{DISH}/option-groups"
    s.limits |= {"menu_max_options_per_group": 2, "menu_option_max_extra_price": 5000,
                 "menu_max_groups_per_store": 3, "menu_max_groups_per_dish": 2}
    s.count, s.links = 2, ["x"]
    assert c.post(create, json=body()).status_code == 200                       # 2 options, 5.000, 3rd group, 2nd on dish
    s.count = 3
    assert c.post(create, json=body()).json()["detail"]["code"] == "groups_per_store_max"
    s.count, s.links = 0, ["x", "y"]
    assert c.post(create, json=body()).json()["detail"]["code"] == "groups_per_dish_max"
    assert c.post(f"/sellers/me/menu/items/{DISH}/option-groups/{s.g}").json()["detail"]["code"] == "groups_per_dish_max"
    s.links = []
    three = body(options=[{"name": "a"}, {"name": "b"}, {"name": "c"}])
    assert c.post(create, json=three).json()["detail"]["code"] == "options_max"
    pricey = body(options=[{"name": "a", "extra_price": 5001}])
    res = c.post(create, json=pricey)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "extra_price_max"


def test_names_swapped_in_one_save_pass(seller_api):   # the database side: g14 (deferrable unique name)
    other = "00000000-0000-4000-8000-0000000000f1"
    url = f"/sellers/me/menu/option-groups/{seller_api.g}"
    swap = body(options=[{"id": COCA, "name": "Pepsi", "extra_price": 5000}, {"name": "Coca-cola"}])
    assert seller_api.client.put(url, json=swap).status_code == 200
    assert [o["name"] for o in seller_api.saved[0][2]] == ["Pepsi", "Coca-cola"]


def test_tc3_67_lower_price_cap_keeps_old_prices(seller_api):
    seller_api.limits["menu_option_max_extra_price"] = 1000
    url = f"/sellers/me/menu/option-groups/{seller_api.g}"
    renamed = body(options=[{"id": COCA, "name": "Coke", "extra_price": 5000}])
    assert seller_api.client.put(url, json=renamed).status_code == 200         # its 5.000 was saved before the cap
    raised = body(options=[{"id": COCA, "name": "Coke", "extra_price": 6000}])
    assert seller_api.client.put(url, json=raised).json()["detail"]["code"] == "extra_price_max"


def test_detach_and_order(seller_api):
    s, c = seller_api, seller_api.client
    s.links = ["first", s.g, "third"]
    assert c.delete(f"/sellers/me/menu/items/{DISH}/option-groups/{s.g}").status_code == 200
    assert s.detached == [(DISH, s.g, SELLER)] and s.deleted == []   # the group stays
    assert s.ordered == [["first", "third"]]   # renumbered 0, 1: the next attach (position 2) is last, not a tie
    s.links = [s.g, s.b]
    assert c.put(f"/sellers/me/menu/items/{DISH}/option-groups", json={"group_ids": [s.g]}).status_code == 400
