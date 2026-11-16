"""Admin Gateway menu edits (flow 20261114-admin-menu-edit, TC-1 to TC-5): the admin backend edits a store's option
groups and a dish's stock / minimum through the seller routes' own code, with the seller_id of the path.
DAOs are faked (same shape as test_option_groups.py); TC-5 is the old seller tests staying green.

Run from tests/backend:  pytest unit/test_admin_menu_edit.py
"""
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import admin_gateway, sellers
from core.auth import verify_token
from dao.dao_menu_option_groups import OptionNameTaken

KEY = "gw_test_key_0123456789"
SELLER, OTHER = "00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000a2"
DISH, DISH_B = "00000000-0000-4000-8000-0000000000d1", "00000000-0000-4000-8000-0000000000d2"
G, G_B = "00000000-0000-4000-8000-0000000000e1", "00000000-0000-4000-8000-0000000000e2"
COCA = "00000000-0000-4000-8000-000000000001"
GW = "/admin-gateway/sellers"
OK = {"X-Api-Key": KEY}


def body(**kw):
    return {"name": "Drinks", "is_required": True, "max_select": 1,
            "options": [{"name": "Coca-cola", "extra_price": 5000}, {"name": "Water"}]} | kw


@pytest.fixture
def env(monkeypatch):
    """Store SELLER owns dish DISH and group G (used by 3 dishes); store OTHER owns dish DISH_B and group G_B."""
    state = SimpleNamespace(saved=[], writes=[], limits=dict(sellers.MENU_LIMITS), updates=[], created=None)
    groups = {(G, SELLER): {"id": G, "name": "Drinks", "is_required": True, "max_select": 1, "dish_ids": [DISH, "x", "y"],
                            "menu_options": [{"id": COCA, "name": "Coca-cola", "extra_price": 4000, "is_available": True,
                                              "sort_order": 0}]},
              (G_B, OTHER): {"id": G_B, "name": "B", "is_required": False, "max_select": 1, "dish_ids": [], "menu_options": []}}
    dishes = {(DISH, SELLER), (DISH_B, OTHER)}

    class Groups:
        def read_group(self, group_id, seller_id):
            found = groups.get((group_id, seller_id))
            return dict(found) if found else None

        def count_store_groups(self, seller_id):
            return 0

        def read_dish_links(self, food_item_id, seller_id):
            return [G] if (food_item_id, seller_id) in dishes else []

        def save_group(self, seller_id, group_id, fields, options):
            state.saved.append((seller_id, group_id, fields, options))
            state.writes.append("save")
            return group_id or G

        def attach(self, *a):
            state.writes.append("attach")

        def detach(self, *a):
            state.writes.append("detach")

        def set_dish_order(self, *a):
            state.writes.append("order")

        def delete_group(self, *a):
            state.writes.append("delete")

    cats = {("00000000-0000-4000-8000-0000000000c1", SELLER), ("00000000-0000-4000-8000-0000000000c2", OTHER)}

    class Cats:
        def is_owned_by_seller(self, category_id, seller_id):
            return (category_id, seller_id) in cats

    class Foods:
        def read_owned_by_seller(self, item_id, seller_id):
            return {"id": item_id} if (item_id, seller_id) in dishes else None

        def update(self, item_id, seller_id, fields):
            if (item_id, seller_id) not in dishes:
                return None
            state.updates.append((item_id, seller_id, fields))
            return {"id": item_id, "stock": fields.get("stock"), "min_quantity": fields.get("min_quantity", 1)}

        def create(self, seller_id, fields):
            state.created = (seller_id, fields)
            return {"id": "new", **fields}

    monkeypatch.setenv("ADMIN_GATEWAY_API_KEY", KEY)
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: SELLER)
    monkeypatch.setattr(sellers, "DAOMenuOptionGroups", Groups)
    monkeypatch.setattr(sellers, "DAOFoodItems", Foods)
    monkeypatch.setattr(sellers, "DAOMenuCategories", Cats)
    monkeypatch.setattr(sellers, "add_sold_out", lambda items: None)
    monkeypatch.setattr(sellers, "_menu_limits", lambda: state.limits)
    app = FastAPI()
    app.include_router(sellers.router)
    app.include_router(admin_gateway.router, prefix="")
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    state.client = TestClient(app, raise_server_exceptions=False)
    return state


# every gateway write route: (method, path, json)
ROUTES = [
    ("patch", f"{GW}/{SELLER}/menu/items/{DISH}", {"stock": 5, "min_quantity": 2}),
    ("post", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups", body()),
    ("put", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups", {"group_ids": [G]}),
    ("post", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups/{G}", None),
    ("delete", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups/{G}", None),
    ("put", f"{GW}/{SELLER}/menu/option-groups/{G}", body()),
    ("delete", f"{GW}/{SELLER}/menu/option-groups/{G}", None),
]


def call(env, method, path, json=None, headers=OK):
    return env.client.request(method.upper(), path, json=json, headers=headers)


@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "wrong"}, {"X-Api-Key": ""}])
@pytest.mark.parametrize("method, path, json", ROUTES)
def test_tc1_no_key_or_wrong_key_writes_nothing(env, method, path, json, headers):
    assert call(env, method, path, json, headers).status_code == 401
    assert env.writes == [] and env.updates == []


def test_tc1_gateway_off_without_a_key(env, monkeypatch):
    monkeypatch.delenv("ADMIN_GATEWAY_API_KEY")
    assert call(env, "put", f"{GW}/{SELLER}/menu/option-groups/{G}", body()).status_code == 503
    assert env.writes == []


def test_tc1_the_routes_are_not_in_the_public_docs(env):
    assert not any(r.path.startswith("/admin-gateway") for r in env.client.app.routes if r.include_in_schema)


# ── TC-2: the path's store is the only store these routes see ──

@pytest.mark.parametrize("method, path, json", [
    ("put", f"{GW}/{SELLER}/menu/option-groups/{G_B}", body()),                          # group of the other store
    ("delete", f"{GW}/{SELLER}/menu/option-groups/{G_B}", None),
    ("patch", f"{GW}/{SELLER}/menu/items/{DISH_B}", {"stock": 1}),                       # dish of the other store
    ("post", f"{GW}/{SELLER}/menu/items/{DISH_B}/option-groups", body()),
    ("put", f"{GW}/{SELLER}/menu/items/{DISH_B}/option-groups", {"group_ids": [G]}),
    ("post", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups/{G_B}", None),              # own dish, other store's group
    ("post", f"{GW}/{SELLER}/menu/items/{DISH_B}/option-groups/{G}", None),              # other store's dish, own group
    ("delete", f"{GW}/{SELLER}/menu/items/{DISH_B}/option-groups/{G}", None),
    ("put", f"{GW}/{OTHER}/menu/option-groups/{G}", body()),                             # the path names the other store
    ("patch", f"{GW}/{OTHER}/menu/items/{DISH}", {"stock": 1}),
    ("put", f"{GW}/00000000-0000-4000-8000-0000000000ff/menu/option-groups/{G}", body()),   # a store that does not exist
])
def test_tc2_other_store_is_404_and_writes_nothing(env, method, path, json):
    res = call(env, method, path, json)
    assert res.status_code == 404, res.text
    assert env.writes == [] and env.updates == []


# ── TC-3: same code as the seller's routes ──

def test_tc3_shared_group_price_change_is_what_the_seller_route_saves(env):
    change = body(options=[{"id": COCA, "name": "Coca-cola", "extra_price": 7000}, {"name": "Water"}])
    via_gateway = call(env, "put", f"{GW}/{SELLER}/menu/option-groups/{G}", change)
    via_seller = env.client.put(f"/sellers/me/menu/option-groups/{G}", json=change)
    assert via_gateway.status_code == via_seller.status_code == 200
    assert via_gateway.json() == via_seller.json()
    assert len(env.saved) == 2 and env.saved[0] == env.saved[1]                 # one group row = the 3 dishes see it
    assert env.saved[0][0] == SELLER and env.saved[0][3][0]["extra_price"] == 7000


def test_tc3_stock_and_minimum_go_through_the_seller_patch(env):
    res = call(env, "patch", f"{GW}/{SELLER}/menu/items/{DISH}", {"stock": 5, "min_quantity": 2})
    assert res.status_code == 200
    [(_, seller_id, fields)] = env.updates
    assert seller_id == SELLER and fields["stock"] == 5 and fields["min_quantity"] == 2 and fields["stock_alert_at"] is None
    call(env, "patch", f"{GW}/{SELLER}/menu/items/{DISH}", {"min_quantity": 3})        # stock left out: not written back
    assert "stock" not in env.updates[1][2]


# ── TC-4: the same limits and errors ──

@pytest.mark.parametrize("change, code", [
    (body(options=[{"name": "Big", "extra_price": 1_000_001}]), "extra_price_max"),
    (body(options=[{"name": f"o{i}"} for i in range(31)]), "options_max"),
])
def test_tc4_limits_answer_like_the_seller_route(env, change, code):
    via_gateway = call(env, "put", f"{GW}/{SELLER}/menu/option-groups/{G}", change)
    via_seller = env.client.put(f"/sellers/me/menu/option-groups/{G}", json=change)
    assert via_gateway.status_code == via_seller.status_code == 400
    assert via_gateway.json() == via_seller.json() and via_gateway.json()["detail"]["code"] == code
    assert env.writes == []


def test_tc4_group_in_use_cannot_be_deleted(env):
    res = call(env, "delete", f"{GW}/{SELLER}/menu/option-groups/{G}")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "group_in_use" and env.writes == []


def test_tc4_duplicate_option_names_are_409(env):
    res = call(env, "put", f"{GW}/{SELLER}/menu/option-groups/{G}", body(options=[{"name": "Coke"}, {"name": "Coke "}]))
    assert res.status_code == 409 and env.writes == []


# ── an edit leaves a line in the app log ──

def test_every_edit_is_logged_with_the_store(env, caplog):
    with caplog.at_level(logging.INFO, logger=admin_gateway.logger.name):
        assert call(env, "post", f"{GW}/{SELLER}/menu/items/{DISH}/option-groups/{G}").status_code == 200
        assert call(env, "patch", f"{GW}/{SELLER}/menu/items/{DISH_B}", {"stock": 1}).status_code == 404
    lines = [r.getMessage() for r in caplog.records if "admin edit" in r.getMessage()]
    assert lines == [f"admin edit seller={SELLER} attach group={G} to dish={DISH}"]   # only edits that happened


# ── a dish goes in a category of the path's store (QA review 14/11) ──

CAT, CAT_B = "00000000-0000-4000-8000-0000000000c1", "00000000-0000-4000-8000-0000000000c2"


def test_dish_category_must_belong_to_the_store(env):
    ok = call(env, "patch", f"{GW}/{SELLER}/menu/items/{DISH}", {"category_id": CAT})
    assert ok.status_code == 200 and env.updates[-1][2]["category_id"] == CAT
    n = len(env.updates)
    for bad in (CAT_B, "00000000-0000-4000-8000-0000000000ff", "not-a-uuid"):   # other store's, unknown, not an id
        res = call(env, "patch", f"{GW}/{SELLER}/menu/items/{DISH}", {"category_id": bad})
        assert res.status_code == 404 and res.json()["detail"] == "Category not found"
    assert len(env.updates) == n


def test_seller_routes_check_the_category_too(env):
    assert env.client.patch(f"/sellers/me/menu/items/{DISH}", json={"category_id": CAT_B}).status_code == 404
    assert env.client.post("/sellers/me/menu/items", json={"name": "A", "price": 1000, "category_id": CAT_B}).status_code == 404
    assert env.updates == [] and env.created is None
    assert env.client.post("/sellers/me/menu/items", json={"name": "A", "price": 1000, "category_id": CAT}).status_code == 200
    assert env.created[0] == SELLER
    assert env.client.post("/sellers/me/menu/items", json={"name": "A", "price": 1000}).status_code == 200   # no category: as before
