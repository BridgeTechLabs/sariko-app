"""T165 + api-perf C / B1 (docs/dev/20261110-api-polling): what the seller list signature, the JWKS cache and
the per-request settings reads must keep doing. No DB, no network."""
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import apis.deliveries as deliveries
import apis.orders as orders
import apis.sellers as sellers
import core.auth as auth
import dao.dao_orders as dao_orders

SRC = Path(dao_orders.__file__).parent.parent


# ── TC-5 / TC-12: every write the seller list shows moves the /head signature ──────────────────────

# DAOOrders methods that write orders without dropping the seller's cached signature, and why that is safe.
NO_INVALIDATE = {
    "create_order": "inserted unpaid; the signature only counts paid rows (update_payment_status drops it)",
    "claim_vnpay_check": "unpaid orders only (read_unpaid_vnpay_orders)",
    "save_vnpay_check": "unpaid orders only",
    "set_vnpay_fail_notified": "unpaid orders only",
    "expire_unpaid_order": "unpaid orders only (T181 A28)",
}


def test_every_orders_write_in_dao_drops_the_signature():  # TC-5
    for name, fn in inspect.getmembers(dao_orders.DAOOrders, inspect.isfunction):
        src = inspect.getsource(fn)
        # a query-builder write starts a chained line (dict.update on a name does not)
        if not re.search(r"(?<![\w\]])\.(update|insert|upsert|delete)\(|\.rpc\(", src):
            continue
        if name in NO_INVALIDATE:
            continue
        assert re.search(r"_invalidate|update_order_status\(", src), f"DAOOrders.{name} writes orders but keeps the cached signature"


def test_orders_is_written_only_by_dao_orders():  # TC-5
    for path in SRC.rglob("*.py"):
        if path.name == "dao_orders.py":
            continue
        for m in re.finditer(r"table\([\"']orders[\"']\)", path.read_text()):
            statement = path.read_text()[m.end():m.end() + 300]
            first = re.search(r"\.(select|update|insert|upsert|delete)\(", statement)
            assert first and first.group(1) == "select", f"{path.relative_to(SRC)} writes orders outside DAOOrders"


def test_every_delivery_write_moves_the_order_signature():  # TC-12
    writers = []
    for module in (deliveries, sellers):
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if fn.__module__ != module.__name__:
                continue
            src = inspect.getsource(fn)
            if re.search(r"\.(update|create)_delivery\(", src):
                writers.append(name)
                assert re.search(r"touch_order\(|update_order_status\(", src), f"{module.__name__}.{name} writes deliveries without touching the order"
    # the known writers (README bước 0b; the buyer's cancel_delivery was removed in T180 A23); a new one must pass the check above
    assert {"delivery_webhook", "allingo_webhook", "rebook_delivery", "update_seller_order_status"} <= set(writers)


# ── TC-8 / TC-19..21: JWKS cached 1 hour, unknown kid refetches ───────────────────────────────────

def _key(kid):
    private = ec.generate_private_key(ec.SECP256R1())
    public = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    return private, {**public, "kid": kid, "alg": "ES256", "use": "sig"}


K1, K2 = _key("k1"), _key("k2")


def _token(key, kid):
    claims = {"sub": "user-1", "aud": "authenticated", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(claims, key[0], algorithm="ES256", headers={"kid": kid})


@pytest.fixture
def jwks(monkeypatch):
    """A fresh client like auth's, whose JWKS endpoint serves `served["keys"]` and counts the fetches."""
    served = {"keys": [K1[1]], "fetches": 0, "down": False}

    def fetch(self):
        served["fetches"] += 1
        data = None if served["down"] else {"keys": list(served["keys"])}
        self.jwk_set_cache.put(data)   # what PyJWT 2.10.1 does in fetch_data's finally: a failure clears the cache
        if data is None:
            raise jwt.PyJWKClientConnectionError("unreachable")
        return data

    client = jwt.PyJWKClient(auth.SUPABASE_JWKS_URL, lifespan=auth.jwks_client.jwk_set_cache.lifespan)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fetch)
    monkeypatch.setattr(auth, "jwks_client", client)
    served["client"] = client
    return served


def verify(token):
    return auth.verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))


def expire(client):
    client.jwk_set_cache.jwk_set_with_timestamp.timestamp -= 3601


def test_jwks_cached_one_hour(jwks):  # TC-8
    assert auth.jwks_client.jwk_set_cache.lifespan == 3600
    for _ in range(5):
        assert verify(_token(K1, "k1"))["id"] == "user-1"
    assert jwks["fetches"] == 1


def test_unknown_kid_is_401_and_refetches_every_time(jwks):  # TC-19: 20 requests = 20 fetches (TODO: rate limit)
    verify(_token(K1, "k1"))
    for _ in range(20):
        with pytest.raises(HTTPException) as e:
            verify(_token(K2, "k2"))
        assert e.value.status_code == 401
    assert jwks["fetches"] == 1 + 20


def test_unreachable_jwks_after_expiry_fails_every_request(jwks):  # TC-20
    verify(_token(K1, "k1"))
    expire(jwks["client"])
    jwks["down"] = True
    for _ in range(3):
        with pytest.raises(HTTPException):
            verify(_token(K1, "k1"))
    jwks["down"] = False
    assert verify(_token(K1, "k1"))["id"] == "user-1"


def test_rotation_new_kid_refetches_once(jwks):  # TC-21a
    verify(_token(K1, "k1"))
    jwks["keys"] = [K1[1], K2[1]]
    assert verify(_token(K2, "k2"))["id"] == "user-1"
    assert verify(_token(K2, "k2"))["id"] == "user-1"
    assert jwks["fetches"] == 2


def test_revoked_key_still_accepted_until_the_hour_ends(jwks):  # TC-21b: accepted risk (api-perf 4C)
    verify(_token(K1, "k1"))
    jwks["keys"] = [K2[1]]
    assert verify(_token(K1, "k1"))["id"] == "user-1"
    expire(jwks["client"])
    with pytest.raises(HTTPException):
        verify(_token(K1, "k1"))


# ── TC-9 / TC-10 / TC-22 / TC-23: settings read once per key per request ──────────────────────────

class CountingSettings:
    reads = []
    minutes = {"buyer_cancel_late_confirmed_minutes": 60, "buyer_cancel_late_delivery_failed_minutes": 30}

    def get_minutes(self, key, default):
        CountingSettings.reads.append(key)
        return timedelta(minutes=CountingSettings.minutes[key])


@pytest.fixture
def settings(monkeypatch):
    CountingSettings.reads = []
    CountingSettings.minutes = dict(CountingSettings.minutes)
    monkeypatch.setattr(sellers, "DAOAdminConfig", CountingSettings)
    monkeypatch.setattr(orders, "DAOAdminConfig", CountingSettings)
    monkeypatch.setattr(sellers, "confirm_window", lambda: timedelta(minutes=30))
    return CountingSettings


NOW = datetime.now(timezone.utc)
SELLER = {"id": "s1", "is_open": True, "weekly_hours": None, "opened_at": None}


def confirmed(minutes_ago, appointment=None):
    return {"status": "confirmed", "payment_status": "paid", "delivery_appointment": appointment,
            "status_changed_at": (NOW - timedelta(minutes=minutes_ago)).isoformat()}


def test_five_confirmed_orders_read_the_setting_once(settings):  # TC-9
    sellers._with_deadlines([confirmed(i) for i in range(5)], SELLER)
    assert settings.reads == ["buyer_cancel_late_confirmed_minutes"]


def test_no_confirmed_order_reads_nothing(settings):  # TC-22
    sellers._with_deadlines([{"status": s, "payment_status": "paid"} for s in ("ready", "done", "cancelled")], SELLER)
    assert settings.reads == []


def test_confirmed_and_failed_deliveries_read_each_setting_once(settings):  # T177 TC-A30a: one read per key
    failed = {**confirmed(40), "status": "delivery_failed"}
    out = sellers._with_deadlines([confirmed(5), dict(failed), confirmed(9), dict(failed)], SELLER)
    assert sorted(settings.reads) == ["buyer_cancel_late_confirmed_minutes", "buyer_cancel_late_delivery_failed_minutes"]
    assert datetime.fromisoformat(out[1]["deadline"]) == datetime.fromisoformat(failed["status_changed_at"]) + timedelta(minutes=30)


def test_deadlines_match_the_single_order_path(settings):  # TC-10, TC-22 (appointment), TC-23
    appointment = (NOW + timedelta(days=1)).isoformat()
    rows = [confirmed(10), confirmed(5, appointment)]
    listed = [o["deadline"] for o in sellers._with_deadlines([dict(r) for r in rows], SELLER)]
    assert listed == [orders.cancel_after(r).isoformat() for r in rows]
    assert datetime.fromisoformat(listed[1]) == datetime.fromisoformat(appointment) + timedelta(minutes=60)
    late = {**confirmed(0), "status": "delivery_failed"}
    assert orders.cancel_after(late) == datetime.fromisoformat(late["status_changed_at"]) + timedelta(minutes=30)


def test_admin_change_applies_to_the_next_request(settings):  # TC-23 (B2 = no cache between requests)
    first = sellers._with_deadlines([confirmed(0)], SELLER)[0]["deadline"]
    settings.minutes["buyer_cancel_late_confirmed_minutes"] = 90
    second = sellers._with_deadlines([confirmed(0)], SELLER)[0]["deadline"]
    assert datetime.fromisoformat(second) - datetime.fromisoformat(first) == timedelta(minutes=30)
    assert settings.reads.count("buyer_cancel_late_confirmed_minutes") == 2


# ── GET /sellers/me/orders keeps the list under the /head signature (docs/dev/20261114-supabase-cost QĐ-7) ──

@pytest.fixture
def seller_list(monkeypatch):
    from core.sariko_cache import cache
    cache.clear()
    state = {"signature": {"latest": "t1", "count": 1}, "list_reads": 0, "head_reads": 0}

    class FakeOrders:
        def read_orders_head_by_seller_id(self, seller_id):
            state["head_reads"] += 1
            return dict(state["signature"])

        def read_orders_by_seller_id(self, seller_id, since):
            state["list_reads"] += 1
            return [{"id": "o1", "status": "done", "payment_status": "paid"}]

    monkeypatch.setattr(sellers, "DAOOrders", FakeOrders)
    monkeypatch.setattr(sellers, "DAOSellerProfiles", lambda: type("P", (), {
        "read_seller_profile_by_user_id": lambda self, uid: {"id": "s1"}})())
    monkeypatch.setattr(sellers, "DAOAdminConfig", lambda: type("C", (), {"get_positive_int": lambda self, k, d: d,
                                                                   "get_minutes": lambda self, k, d: timedelta(minutes=d)})())
    yield state
    cache.clear()


def test_same_signature_returns_the_stored_list_without_a_query(seller_list):
    first = sellers.get_seller_orders(user={"id": "u1"})
    second = sellers.get_seller_orders(user={"id": "u1"})
    assert seller_list["list_reads"] == 1 and first == second
    first["orders"][0]["deadline"] = "x"   # a caller's edit never reaches the stored list
    assert "deadline" not in sellers.cache.get("seller_s1_orders_list")[1][0]


def test_moved_signature_reads_the_list_again(seller_list):
    sellers.get_seller_orders(user={"id": "u1"})
    seller_list["signature"] = {"latest": "t2", "count": 2}
    sellers.cache.invalidate("seller_s1_orders")   # the 30 s signature cache expiring
    sellers.get_seller_orders(user={"id": "u1"})
    assert seller_list["list_reads"] == 2


def test_an_order_write_through_dao_orders_drops_the_list(seller_list):
    sellers.get_seller_orders(user={"id": "u1"})
    dao_orders._invalidate_seller_orders("s1")
    sellers.get_seller_orders(user={"id": "u1"})
    assert seller_list["list_reads"] == 2 and seller_list["head_reads"] == 2
