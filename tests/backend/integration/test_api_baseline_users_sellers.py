"""Regression baseline R1 (docs/dev/regression-baseline): the /users and /sellers routes no other test
reached. One passing case + the main error per route, status code and JSON shape as served today, so the
error-block cleanup keeps them. DAOs and storage are faked; no DB, no network.

Run from tests/backend:  pytest integration/test_api_baseline_users_sellers.py
"""
import pytest

from apis import sellers, users
from core.sariko_cache import cache

SELLER = {"id": "s1", "user_id": "u1", "is_open": True, "opening_time": None, "closing_time": None,
          "avatar_url": "https://img/a.jpg", "phone": "+84901234567"}
VALIDATION = {"detail", "errors"}   # main.validation_exception_handler


class Boom:
    """Any DAO whose every call fails like a dropped DB connection."""
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        def fail(*a, **k):
            raise RuntimeError("db down")
        return fail


@pytest.fixture
def profiles(monkeypatch):
    """DAOSellerProfiles fake in both modules; .profile = the signed-in user's seller row (None = buyer)."""
    class Profiles:
        profile = dict(SELLER)
        updated = []

        def read_seller_profile_by_user_id(self, user_id):
            return Profiles.profile

        def update_seller_profile_info(self, user_id, fields):
            Profiles.updated.append(fields)
            return {**Profiles.profile, **fields} if Profiles.profile else None

        def read_founding_sellers(self):
            return [{"id": "s1", "store_name": "Bếp A"}]

        def read_seller_by_slug_name(self, slug):
            return {"id": "s1", "slug": slug, "tier": "founding"} if slug == "bep-a" else None

    Profiles.updated = []
    monkeypatch.setattr(users, "DAOSellerProfiles", Profiles)
    monkeypatch.setattr(sellers, "DAOSellerProfiles", Profiles)
    return Profiles


# ── /users ──────────────────────────────────────────────────────────────────

def test_users_info_me_buyer_and_seller(api, monkeypatch, profiles):
    class Users:
        row = {"id": "u1", "name": "An", "is_seller": False}

        def get_users(self, user_id):
            return dict(Users.row)

    monkeypatch.setattr(users, "DAOUsers", Users)
    c = api(users.router)
    assert c.get("/users/info/me").json() == {"success": True, "user": {"id": "u1", "name": "An", "is_seller": False}}
    Users.row["is_seller"] = True
    user = c.get("/users/info/me").json()["user"]
    assert (user["seller_id"], user["avatar_url"], user["phone"]) == ("s1", "https://img/a.jpg", "+84901234567")


def test_users_info_me_db_error_is_500(api, monkeypatch):
    monkeypatch.setattr(users, "DAOUsers", Boom)
    r = api(users.router).get("/users/info/me")
    assert r.status_code == 500 and set(r.json()) == {"detail"}


@pytest.mark.parametrize("profile,prefix", [(SELLER, "avatar-sellers/s1/"), (None, "avatar-buyers/u1/")])
def test_users_avatar_path_by_role(api, monkeypatch, profiles, profile, prefix):
    profiles.profile = profile
    seen = []
    monkeypatch.setattr(users, "upload_image_base64", lambda path, data: seen.append(path) or f"https://cdn/{path}")
    r = api(users.router).post("/users/me/avatar", json={"image_base64": "aGk="})
    assert r.status_code == 200 and seen == [prefix + "avatar.jpg"]
    assert set(r.json()) == {"success", "avatar_url"} and r.json()["avatar_url"].startswith(f"https://cdn/{prefix}avatar.jpg?v=")


def test_users_avatar_without_image_is_422(api):
    r = api(users.router).post("/users/me/avatar", json={})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


def test_users_default_address(api, monkeypatch):
    class Addresses:
        def read_default_address(self, user_id):
            return {"id": "a1", "address": "1 Lê Lợi"}

    monkeypatch.setattr(users, "DAOUserAddresses", Addresses)
    assert api(users.router).get("/users/me/address").json() == {"success": True, "address": {"id": "a1", "address": "1 Lê Lợi"}}
    monkeypatch.setattr(users, "DAOUserAddresses", Boom)
    r = api(users.router).get("/users/me/address")
    assert r.status_code == 500 and set(r.json()) == {"detail"}


def test_users_push_subscription(api, monkeypatch):
    saved = []

    class Subs:
        def upsert_subscription(self, **kw):
            saved.append(kw)

    monkeypatch.setattr(users, "DAOPushSubscriptions", Subs)
    keys = {"p256dh": "pk", "auth": "ak"}
    r = api(users.router).post("/users/me/push-subscriptions", json={"endpoint": "https://fcm.googleapis.com/x", "keys": keys})
    assert r.json() == {"success": True}
    assert saved == [{"user_id": "u1", "endpoint": "https://fcm.googleapis.com/x", "p256dh": "pk", "auth": "ak"}]


@pytest.mark.parametrize("endpoint", ["http://fcm.googleapis.com/x", "https://evil.example/x", "https://fcm.googleapis.com.evil.io/x"])
def test_users_push_subscription_only_push_services(api, monkeypatch, endpoint):
    monkeypatch.setattr(users, "DAOPushSubscriptions", Boom)   # never reached
    r = api(users.router).post("/users/me/push-subscriptions", json={"endpoint": endpoint, "keys": {"p256dh": "p", "auth": "a"}})
    assert r.status_code >= 400   # 500 today, see the xfail below


@pytest.mark.xfail(strict=True, reason="main.validation_exception_handler returns exc.errors() whose ctx holds the "
                   "ValueError of a custom validator: not JSON serializable, so the buyer gets 500. Fix = jsonable_encoder; "
                   "then drop this mark (README PHÁT HIỆN)")
@pytest.mark.parametrize("router,method,path,body", [
    ("users", "post", "/users/me/push-subscriptions", {"endpoint": "https://evil.example/x", "keys": {"p256dh": "p", "auth": "a"}}),
    ("sellers", "patch", "/sellers/me/hours", {"opening_time": "09:00"}),
])
def test_custom_validator_errors_should_be_422(api, profiles, router, method, path, body):
    r = api({"users": users, "sellers": sellers}[router].router).request(method.upper(), path, json=body)
    assert r.status_code == 422 and set(r.json()) == VALIDATION


# ── /sellers: public ────────────────────────────────────────────────────────

@pytest.mark.parametrize("module,path", [(users, "/users/info/someone"), (sellers, "/sellers/")])
def test_empty_stub_routes_answer_null(api, module, path):
    r = api(module.router).get(path)
    assert r.status_code == 200 and r.json() is None   # body is `pass` (README PHÁT HIỆN)


def test_sellers_founding(api, monkeypatch, profiles):
    assert api(sellers.router, user=None).get("/sellers/founding").json() == {
        "success": True, "founding_sellers": [{"id": "s1", "store_name": "Bếp A"}]}
    monkeypatch.setattr(sellers, "DAOSellerProfiles", Boom)
    r = api(sellers.router, user=None).get("/sellers/founding")
    assert r.status_code == 500 and r.json() == {"detail": "Internal server error"}   # no try: global handler


def test_sellers_featured_dishes(api, monkeypatch):
    class Items:
        def read_featured_dishes(self):
            return [{"id": "f1"}]

    monkeypatch.setattr(sellers, "DAOFoodItems", Items)
    assert api(sellers.router, user=None).get("/sellers/featured-dishes").json() == {"success": True, "featured_dishes": [{"id": "f1"}]}
    monkeypatch.setattr(sellers, "DAOFoodItems", Boom)
    r = api(sellers.router, user=None).get("/sellers/featured-dishes")
    assert r.status_code == 500 and set(r.json()) == {"detail"}


def test_sellers_public_menu(api, monkeypatch, profiles):
    class Items:
        menu = None

        def read_menu_by_seller_id(self, seller_id):
            return Items.menu

    monkeypatch.setattr(sellers, "DAOFoodItems", Items)
    c = api(sellers.router, user=None)
    assert c.get("/sellers/bep-a/menu").json() == {"success": True, "menus": []}   # None -> []
    Items.menu = [{"id": "f1"}]
    assert c.get("/sellers/bep-a/menu").json()["menus"] == [{"id": "f1"}]
    r = c.get("/sellers/nope/menu")
    assert r.status_code == 404 and r.json() == {"detail": "Seller not found"}


# ── /sellers/me ─────────────────────────────────────────────────────────────

def test_sellers_open_switch(api, profiles):
    r = api(sellers.router).patch("/sellers/me/open", json={"is_open": False})
    assert r.json() == {"success": True, "is_open": False, "open_now": False} and profiles.updated == [{"is_open": False}]


@pytest.mark.parametrize("path,body", [("/sellers/me/open", {"is_open": True}),
                                       ("/sellers/me/hours", {"opening_time": "09:00", "closing_time": "20:00"})])
def test_sellers_store_settings_refuse_a_buyer(api, profiles, path, body):
    profiles.profile = None
    r = api(sellers.router).patch(path, json=body)
    assert r.status_code == 403 and r.json() == {"detail": "User is not a seller"}


def test_sellers_hours(api, profiles):
    r = api(sellers.router).patch("/sellers/me/hours", json={"opening_time": "09:00", "closing_time": "20:00"})
    assert r.status_code == 200 and set(r.json()) == {"success", "opening_time", "closing_time", "open_now"}
    assert profiles.updated == [{"opening_time": "09:00:00", "closing_time": "20:00:00"}]
    r = api(sellers.router).patch("/sellers/me/hours", json={"opening_time": None, "closing_time": None})
    assert r.json()["opening_time"] is None and r.json()["closing_time"] is None   # all day


def test_sellers_open_switch_needs_a_bool(api, profiles):
    r = api(sellers.router).patch("/sellers/me/open", json={"is_open": "maybe"})
    assert r.status_code == 422 and set(r.json()) == VALIDATION and profiles.updated == []


def test_sellers_orders_head_cached_until_written(api, monkeypatch, profiles):
    reads = []

    class Orders:
        def read_orders_head_by_seller_id(self, seller_id):
            reads.append(seller_id)
            return {"count": 3, "updated_at": "2026-10-29T00:00:00+00:00"}

    monkeypatch.setattr(sellers, "DAOOrders", Orders)
    cache.clear()
    c = api(sellers.router)
    first, second = c.get("/sellers/me/orders/head").json(), c.get("/sellers/me/orders/head").json()
    assert first == {"success": True, "cached": False, "count": 3, "updated_at": "2026-10-29T00:00:00+00:00"}
    assert second["cached"] is True and reads == ["s1"]
    cache.clear()


def test_sellers_menu(api, monkeypatch, profiles):
    class Items:
        def read_menu_by_seller_id(self, seller_id):
            return [{"id": "f1", "seller_id": seller_id}]

    monkeypatch.setattr(sellers, "DAOFoodItems", Items)
    assert api(sellers.router).get("/sellers/me/menu").json() == {"success": True, "menu": [{"id": "f1", "seller_id": "s1"}]}


@pytest.mark.parametrize("method,path", [("get", "/sellers/me/orders/head"), ("get", "/sellers/me/menu"),
                                         ("delete", "/sellers/me/menu/categories/c1"),
                                         ("post", "/sellers/me/menu/categories"),
                                         ("post", "/sellers/me/menu/items/f1/image"),
                                         ("patch", "/sellers/me/menu/variants/v1")])
def test_sellers_me_routes_refuse_a_buyer(api, profiles, method, path):
    profiles.profile = None
    body = {"post": {"name": "Ulam", "image_base64": "aGk="}, "patch": {"price": 1000}}.get(method)
    r = api(sellers.router).request(method.upper(), path, json=body)
    assert r.status_code == 403 and r.json() == {"detail": "User is not a seller"}


def test_sellers_create_and_delete_category(api, monkeypatch, profiles):
    calls = []

    class Categories:
        def create(self, seller_id, name, sort_order):
            calls.append(("create", seller_id, name, sort_order))
            return {"id": "c1", "name": name}

        def delete(self, cat_id, seller_id):
            calls.append(("delete", cat_id, seller_id))

    monkeypatch.setattr(sellers, "DAOMenuCategories", Categories)
    c = api(sellers.router)
    assert c.post("/sellers/me/menu/categories", json={"name": "Ulam"}).json() == {"success": True, "category": {"id": "c1", "name": "Ulam"}}
    assert c.delete("/sellers/me/menu/categories/c1").json() == {"success": True}
    assert calls == [("create", "s1", "Ulam", 0), ("delete", "c1", "s1")]
    r = c.post("/sellers/me/menu/categories", json={"name": ""})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


@pytest.fixture
def variants(monkeypatch, profiles):
    class Variants:
        updates = []

        def read_parent_item_id(self, variant_id):
            return {"v1": "f1", "v2": "f-other"}.get(variant_id)

        def update(self, variant_id, fields):
            Variants.updates.append((variant_id, fields))
            return {"id": variant_id, **fields}

    class Items:
        def read_owned_by_seller(self, item_id, seller_id):
            return item_id == "f1"

    Variants.updates = []
    monkeypatch.setattr(sellers, "DAOFoodItemVariants", Variants)
    monkeypatch.setattr(sellers, "DAOFoodItems", Items)
    return Variants


def test_sellers_update_variant(api, variants):
    r = api(sellers.router).patch("/sellers/me/menu/variants/v1", json={"price": 75000})
    assert r.json() == {"success": True, "variant": {"id": "v1", "price": 75000, "price_text": "75.000 ₫"}}


@pytest.mark.parametrize("variant_id,body,status,detail", [
    ("v2", {"price": 1000}, 404, "Variant not found"),        # another seller's dish
    ("v9", {"price": 1000}, 404, "Variant not found"),        # no such variant
    ("v1", {}, 400, "No fields to update"),
])
def test_sellers_update_variant_errors(api, variants, variant_id, body, status, detail):
    r = api(sellers.router).patch(f"/sellers/me/menu/variants/{variant_id}", json=body)
    assert r.status_code == status and r.json() == {"detail": detail} and variants.updates == []


def test_sellers_update_variant_price_must_be_positive(api, variants):
    r = api(sellers.router).patch("/sellers/me/menu/variants/v1", json={"price": 0})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


def test_sellers_dish_image(api, monkeypatch, profiles):
    seen = []
    monkeypatch.setattr(sellers, "upload_image_base64", lambda path, data: seen.append(path) or f"https://cdn/{path}")
    r = api(sellers.router).post("/sellers/me/menu/items/f1/image", json={"image_base64": "aGk="})
    assert r.status_code == 200 and set(r.json()) == {"success", "image_url"}
    assert seen[0].startswith("food-items/s1/f1-") and r.json()["image_url"] == f"https://cdn/{seen[0]}"
    r = api(sellers.router).post("/sellers/me/menu/items/f1/image", json={})
    assert r.status_code == 422 and set(r.json()) == VALIDATION
