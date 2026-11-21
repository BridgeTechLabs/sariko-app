"""Public home banners (docs/dev/20261121-promo-banners TC-1, 2, 3, 17). The Supabase client is faked."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import promo_banners
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_promo_banners import DAOPromoBanners

ROWS = [  # as in the table, unordered
    {"id": "c", "image_url": "https://x/c.webp", "link_url": "https://c", "alt": "", "position": 2, "created_at": "1", "is_active": True},
    {"id": "off", "image_url": "https://x/o.webp", "link_url": "https://o", "alt": "", "position": 0, "created_at": "1", "is_active": False},
    {"id": "b", "image_url": "https://x/b.webp", "link_url": "https://b", "alt": "B", "position": 1, "created_at": "2", "is_active": True},
    {"id": "a", "image_url": "https://x/a.webp", "link_url": "https://a", "alt": "A", "position": 1, "created_at": "1", "is_active": True},
]


class FakeClient:
    """Applies the query the DAO builds to ROWS."""

    def __init__(self):
        self.reads, self.down = 0, False

    def table(self, name):
        assert name == "admin_promo_banners"
        self._eq, self._order, self._limit = {}, [], None
        return self

    def select(self, cols):
        self._cols = [c.strip() for c in cols.split(",")]
        return self

    def eq(self, col, value):
        self._eq[col] = value
        return self

    def order(self, col):
        self._order.append(col)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        self.reads += 1
        if self.down:
            raise Exception("db down")
        rows = [r for r in ROWS if all(r[k] == v for k, v in self._eq.items())]
        rows.sort(key=lambda r: tuple(r[c] for c in self._order))
        return type("R", (), {"data": [{c: r[c] for c in self._cols} for r in rows[:self._limit]]})()


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(DAOPromoBanners, "__init__", lambda self: setattr(self, "_supabase_client", fake))
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_setting", lambda self, k: {"promo_banner_max": 2}.get(k))
    app = FastAPI()
    app.include_router(promo_banners.router, prefix="/rest/v1")
    return TestClient(app), fake


def ids(body):
    return [b["id"] for b in body["banners"]]


def test_tc1_active_only_in_order_capped_no_token(client):  # TC-1
    http, _ = client
    body = http.get("/rest/v1/promo-banners").json()
    assert body["success"] is True
    assert ids(body) == ["a", "b"]   # position, then created_at; "off" hidden; promo_banner_max = 2 cuts "c"
    assert set(body["banners"][0]) == {"id", "image_url", "link_url", "alt"}


def test_tc2_second_read_within_60s_is_cached(client):  # TC-2
    http, fake = client
    http.get("/rest/v1/promo-banners")
    assert ids(http.get("/rest/v1/promo-banners").json()) == ["a", "b"]
    assert fake.reads == 1


def test_tc3_tc17_db_error_returns_empty_and_is_not_cached(client, caplog):  # TC-3, TC-17
    http, fake = client
    fake.down = True
    resp = http.get("/rest/v1/promo-banners")
    assert resp.status_code == 200 and resp.json() == {"success": True, "banners": []}
    assert sum("[PromoBanners]" in r.message for r in caplog.records) == 1
    fake.down = False
    assert ids(http.get("/rest/v1/promo-banners").json()) == ["a", "b"]
