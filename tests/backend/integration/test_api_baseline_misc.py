"""Regression baseline R1 (docs/dev/regression-baseline): /address, /search, /chat, /dev, /moit, /health,
plus auth for EVERY route: no token / a bad token on each verify_token route of the real app, and
verify_token itself (expired, wrong audience, another key). Goong is an httpx MockTransport; DAOs are faked.

Run from tests/backend:  pytest integration/test_api_baseline_misc.py
"""
import importlib
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from apis import address, chat, dev, moit, search
from core import auth

VALIDATION = {"detail", "errors"}


# ── /address (Goong) ────────────────────────────────────────────────────────

@pytest.fixture
def goong(monkeypatch):
    """.answer = (status, json) Goong sends back; .asked = the paths we called."""
    state = SimpleNamespace(answer=(200, {}), asked=[])

    def handler(request):
        state.asked.append(request.url.path)
        return httpx.Response(state.answer[0], json=state.answer[1])

    real_client = httpx.Client
    monkeypatch.setattr(address.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(address, "GOONG_API_KEY", "test-key")
    return state


def test_address_search(api, goong):
    goong.answer = (200, {"predictions": [{"place_id": "p1", "description": "1 Lê Lợi, Q1",
                                           "structured_formatting": {"main_text": "1 Lê Lợi", "secondary_text": "Q1"}}]})
    r = api(address.router).get("/address/search", params={"q": "le loi"})
    assert r.json() == {"success": True, "results": [{"place_id": "p1", "label": "1 Lê Lợi, Q1", "main_text": "1 Lê Lợi", "secondary_text": "Q1"}]}
    assert goong.asked == ["/Place/AutoComplete"]


def test_address_detail_and_reverse(api, goong):
    goong.answer = (200, {"result": {"geometry": {"location": {"lat": 10.77, "lng": 106.7}}, "formatted_address": "1 Lê Lợi", "name": "Chợ"}})
    assert api(address.router).get("/address/detail", params={"place_id": "p1"}).json() == {
        "success": True, "lat": 10.77, "lon": 106.7, "address": "1 Lê Lợi", "name": "Chợ"}
    goong.answer = (200, {"results": [{"formatted_address": "2 Hai Bà Trưng"}]})
    assert api(address.router).get("/address/reverse", params={"lat": 10.7, "lon": 106.7}).json() == {"success": True, "address": "2 Hai Bà Trưng"}
    goong.answer = (200, {"results": []})
    assert api(address.router).get("/address/reverse", params={"lat": 10.7, "lon": 106.7}).json() == {"success": True, "address": None}


@pytest.mark.parametrize("path,params,detail", [("/address/search", {"q": "le loi"}, "Address search failed"),
                                                ("/address/detail", {"place_id": "p1"}, "Place detail failed"),
                                                ("/address/reverse", {"lat": 1, "lon": 1}, "Reverse geocode failed")])
def test_address_goong_error_is_502(api, goong, path, params, detail):
    goong.answer = (500, {"error": "down"})
    r = api(address.router).get(path, params=params)
    assert r.status_code == 502 and r.json() == {"detail": detail}


def test_address_errors(api, goong, monkeypatch):
    goong.answer = (200, {"result": {}})
    r = api(address.router).get("/address/detail", params={"place_id": "p1"})
    assert r.status_code == 404 and r.json() == {"detail": "Place not found"}
    for path, params in (("/address/search", {"q": "a"}), ("/address/reverse", {"lat": "x", "lon": 1})):
        r = api(address.router).get(path, params=params)
        assert r.status_code == 422 and set(r.json()) == VALIDATION
    monkeypatch.setattr(address, "GOONG_API_KEY", "")
    goong.asked.clear()
    r = api(address.router).get("/address/search", params={"q": "le loi"})
    assert r.status_code == 503 and r.json() == {"detail": "Address service not configured (missing GOONG_API_KEY)"} and goong.asked == []


# ── /search (public) ────────────────────────────────────────────────────────

def test_search(api, monkeypatch):
    asked = []
    food = {"id": "f1", "name": "Adobo", "image_url": None, "preorder_day": None, "menu_categories": {"name": "Ulam"},
            "seller_profiles": {"slug": "bep-a", "store_name": "Bếp A", "avatar_url": None}}
    monkeypatch.setattr(search, "DAOFoodItems", lambda: SimpleNamespace(search_by_name=lambda q: asked.append(q) or [food]))
    monkeypatch.setattr(search, "DAOMenuCategories", lambda: SimpleNamespace(search_by_name=lambda q: [{"name": "Ulam", "seller_profiles": None}]))
    c = api(search.router, user=None)
    assert c.get("/search", params={"q": "  "}).json() == {"foods": [], "categories": []} and asked == []
    r = c.get("/search", params={"q": " 50%_off "}).json()
    assert asked == ["50\\%\\_off"]   # ILIKE wildcards escaped
    assert r == {"foods": [{"id": "f1", "name": "Adobo", "image_url": None, "preorder_day": 0, "category": "Ulam",
                            "seller": {"slug": "bep-a", "store_name": "Bếp A", "avatar_url": None}}],
                 "categories": [{"name": "Ulam", "seller": {"slug": None, "store_name": None, "avatar_url": None}}]}
    r = c.get("/search", params={"q": "x" * 101})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


# ── /chat ───────────────────────────────────────────────────────────────────

CONV = {"id": "c1", "buyer_id": "u1", "seller_id": "s1", "buyer_pinned_at": "2026-10-29", "seller_pinned_at": None}


@pytest.fixture
def chats(monkeypatch):
    """Caller u1 is the buyer of c1; .profile = u1's seller row (None = not a seller); .log = DAO writes."""
    state = SimpleNamespace(profile=None, conv=dict(CONV), log=[], owner={"user_id": "u9"})

    class Sellers:
        def read_seller_by_slug_name(self, slug):
            return {"id": "s1"} if slug == "bep-a" else None

        def read_seller_user_id_by_seller_id(self, seller_id):
            return state.owner

        def read_seller_profile_by_user_id(self, user_id):
            return state.profile

    class Convs:
        def get_or_create(self, buyer_id, seller_id):
            state.log.append(("get_or_create", buyer_id, seller_id))
            return {"id": "c1"}

        def read_by_id(self, conversation_id):
            return state.conv if conversation_id == "c1" else None

        def list_for_buyer(self, user_id):
            return [dict(CONV)]

        def list_for_seller(self, seller_id):
            return [dict(CONV, id="c2", buyer_id="u3"), dict(CONV, id="c3", buyer_id="u1")]   # c3: own store

        def set_pinned(self, cid, side, pinned):
            state.log.append(("pin", cid, side, pinned))

        def soft_delete(self, cid, side):
            state.log.append(("delete", cid, side))

    class Messages:
        def read_unread_rows(self, ids, reader_id):
            return [{"conversation_id": i} for i in ids for _ in range(2)]

        def mark_read(self, conversation_id, reader_id):
            state.log.append(("read", conversation_id, reader_id))

    monkeypatch.setattr(chat, "DAOSellerProfiles", Sellers)
    monkeypatch.setattr(chat, "DAOChatConversations", Convs)
    monkeypatch.setattr(chat, "DAOChatMessages", Messages)
    return state


def test_chat_open_conversation(api, chats):
    c = api(chat.router)
    assert c.post("/chat/conversations", json={"seller_slug": "bep-a"}).json() == {"success": True, "conversation": {"id": "c1"}}
    assert chats.log == [("get_or_create", "u1", "s1")]
    r = c.post("/chat/conversations", json={"seller_slug": "nope"})
    assert r.status_code == 404 and r.json() == {"detail": "Seller not found"}
    chats.owner = {"user_id": "u1"}
    r = c.post("/chat/conversations", json={"seller_slug": "bep-a"})
    assert r.status_code == 400 and r.json() == {"detail": "Cannot start a conversation with your own store"}
    r = c.post("/chat/conversations", json={})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


def test_chat_list_buyer_and_seller(api, chats):
    c = api(chat.router)
    [conv] = c.get("/chat/conversations").json()["conversations"]
    assert (conv["id"], conv["unread_count"], conv["pinned"]) == ("c1", 2, True)
    r = c.get("/chat/conversations", params={"as_seller": True})
    assert r.status_code == 403 and r.json() == {"detail": "Not a seller"}
    chats.profile = {"id": "s1"}
    convs = c.get("/chat/conversations", params={"as_seller": True}).json()["conversations"]
    assert [(x["id"], x["pinned"]) for x in convs] == [("c2", False)]   # no conversation with one's own store


@pytest.mark.parametrize("method,suffix,body,log", [
    ("patch", "/read", None, ("read", "c1", "u1")),
    ("patch", "/pin", {"pinned": False}, ("pin", "c1", "buyer", False)),
    ("delete", "", None, ("delete", "c1", "buyer")),
])
def test_chat_conversation_actions(api, chats, method, suffix, body, log):
    c = api(chat.router)
    r = c.request(method.upper(), f"/chat/conversations/c1{suffix}", json=body)
    assert r.status_code == 200 and r.json()["success"] is True and chats.log == [log]
    r = c.request(method.upper(), f"/chat/conversations/c9{suffix}", json=body)
    assert r.status_code == 404 and r.json() == {"detail": "Conversation not found"}
    chats.conv = dict(CONV, buyer_id="u3", seller_id="s9")   # someone else's conversation
    r = c.request(method.upper(), f"/chat/conversations/c1{suffix}", json=body)
    assert r.status_code == 403 and r.json() == {"detail": "Forbidden"} and len(chats.log) == 1


def test_chat_pin_as_seller(api, chats):
    chats.conv, chats.profile = dict(CONV, buyer_id="u3"), {"id": "s1"}
    assert api(chat.router).patch("/chat/conversations/c1/pin", json={"pinned": True}).json() == {"success": True, "pinned": True}
    assert chats.log == [("pin", "c1", "seller", True)]


# ── /dev (local + DEV only) ─────────────────────────────────────────────────

def test_dev_force_routes(api, monkeypatch):
    log = []
    monkeypatch.setattr(dev, "DAOOrders", lambda: SimpleNamespace(update_payment_status=lambda o, s: log.append(("pay", o, s)),
                                                                  update_order_status=lambda o, s: log.append(("status", o, s))))
    c = api(dev.router)
    assert c.patch("/dev/orders/o1/force-pay").json() == {"success": True}
    assert c.patch("/dev/orders/o1/force-unpay").json() == {"success": True}
    assert c.patch("/dev/orders/o1/force-status", json={"status": "ready"}).json() == {"success": True}
    assert log == [("pay", "o1", "paid"), ("pay", "o1", "pending"), ("status", "o1", "ready")]
    r = c.patch("/dev/orders/o1/force-status", json={"status": "delivery_failed"})
    assert r.status_code == 400 and r.json() == {"detail": "Invalid status"} and len(log) == 3


@pytest.mark.parametrize("env,mounted", [("local", True), ("dev", True), ("prod", False)])
def test_dev_routes_never_on_prod(monkeypatch, tmp_path, env, mounted):
    monkeypatch.chdir(tmp_path)
    import main
    monkeypatch.setenv("ENV", env)
    try:
        paths = {r.path for r in importlib.reload(main).app.routes}
    finally:
        monkeypatch.undo()
        monkeypatch.chdir(tmp_path)
        importlib.reload(main)
    assert ("/rest/v1/dev/orders/{order_id}/force-pay" in paths) is mounted


# ── /moit/report (Bộ Công Thương pulls our numbers) ─────────────────────────

COUNTS = {"count_users_total": 120, "count_sellers_total": 48, "count_sellers_new": 40, "count_food_items_total": 300,
          "count_food_items_new": 280, "count_orders_total": 90, "count_orders_done": 80, "count_orders_cancelled": 10,
          "sum_done_orders_value": 7_500_000}


@pytest.fixture
def moit_env(monkeypatch):
    monkeypatch.setenv("MOIT_API_USERNAME", "moit")
    monkeypatch.setenv("MOIT_API_PASSWORD", "secret")
    monkeypatch.setattr(moit, "DAOMoitReport", lambda: SimpleNamespace(**{k: (lambda *a, v=v: v) for k, v in COUNTS.items()}))


def test_moit_report(api, moit_env):
    r = api(moit.router, user=None).post("/moit/report", json={"UserName": "moit", "PassWord": "secret"})
    assert r.json() == {"soLuongTruyCap": 120, "soNguoiBan": 48, "soNguoiBanMoi": 40, "tongSoSanPham": 300, "soSanPhamMoi": 280,
                        "soLuongGiaoDich": 90, "tongSoDonHangThanhCong": 80, "tongSoDonHangKhongThanhCong": 10,
                        "tongGiaTriGiaoDich": 7_500_000}


@pytest.mark.parametrize("body", [{"UserName": "moit", "PassWord": "wrong"}, {"UserName": "x", "PassWord": "secret"}])
def test_moit_wrong_credentials(api, moit_env, body):
    r = api(moit.router, user=None).post("/moit/report", json=body)
    assert r.status_code == 401 and r.json() == {"detail": "Invalid credentials"}


def test_moit_not_configured_and_bad_body(api, moit_env, monkeypatch):
    monkeypatch.setenv("MOIT_API_PASSWORD", "")
    r = api(moit.router, user=None).post("/moit/report", json={"UserName": "moit", "PassWord": ""})
    assert r.status_code == 500 and r.json() == {"detail": "Server not configured"}   # fail closed
    r = api(moit.router, user=None).post("/moit/report", json={"UserName": "moit"})
    assert r.status_code == 422 and set(r.json()) == VALIDATION


# ── /health and auth on the real app ────────────────────────────────────────

@pytest.fixture
def real_app(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    import main
    return main.app


def test_health(real_app, monkeypatch):
    monkeypatch.setenv("IMAGE_TAG", "7dbb356")
    assert TestClient(real_app).get("/health").json() == {"success": True, "status": "ok", "version": "7dbb356", "service": "sariko-api"}


def _protected(app):
    """(method, path) of every route that depends on verify_token, path params filled in."""
    def uses_token(dependant):
        return any(d.call is auth.verify_token or uses_token(d) for d in dependant.dependencies)

    return sorted((m, r.path.replace("{", "").replace("}", "")) for r in app.routes
                  if getattr(r, "dependant", None) and uses_token(r.dependant) for m in r.methods)


@pytest.mark.parametrize("token,status,detail", [(None, 403, "Not authenticated"), ("not-a-jwt", 401, "Unauthorized")])
def test_every_protected_route_refuses_without_a_valid_token(real_app, token, status, detail):
    client = TestClient(real_app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    routes = _protected(real_app)
    assert len(routes) >= 60   # an empty list would pass silently (64 in the CI image, 65 locally: /dev is mounted only when ENV is local / dev)
    wrong = [(m, p, r.status_code) for m, p in routes
             for r in [client.request(m, p, headers=headers)] if (r.status_code, r.json()) != (status, {"detail": detail})]
    assert wrong == []


@pytest.fixture
def signing_key(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth.jwks_client, "get_signing_key_from_jwt", lambda token: SimpleNamespace(key=key.public_key()))
    return key


def _token(key, **claims):
    payload = {"sub": "u1", "aud": "authenticated", "exp": int(time.time()) + 600, "user_metadata": {"fullname": "An"}} | claims
    return jwt.encode(payload, key, algorithm="ES256")


def _verify(token):
    return auth.verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))


def test_verify_token_valid(signing_key):
    assert _verify(_token(signing_key)) == {"id": "u1", "fullname": "An"}


@pytest.mark.parametrize("claims,other_key", [({"exp": int(time.time()) - 10}, False), ({"aud": "anon"}, False), ({}, True)])
def test_verify_token_rejects(signing_key, claims, other_key):
    key = ec.generate_private_key(ec.SECP256R1()) if other_key else signing_key
    with pytest.raises(HTTPException) as e:
        _verify(_token(key, **claims))
    assert e.value.status_code == 401


def test_verify_token_rejects_hs256_signed_with_the_public_key(signing_key):
    with pytest.raises(HTTPException) as e:
        _verify(jwt.encode({"sub": "u1", "aud": "authenticated"}, "public-key-as-secret", algorithm="HS256"))
    assert e.value.status_code == 401
