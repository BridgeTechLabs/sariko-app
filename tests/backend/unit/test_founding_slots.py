"""Founding places left = admin_settings.founding_slots - sellers on the founding plan.
No DB, no network.

Run from tests/backend:  pytest unit/test_founding_slots.py
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from dao.dao_admin_config import DAOAdminConfig


class FakeConfig:
    raw = {}

    def get_positive_int(self, key, default):
        return DAOAdminConfig._positive_int(key, self.raw.get(key), default)


class FakeProfiles:
    def count_sellers_by_tier(self, tier):
        assert tier == "founding"
        return 12


def _slots(monkeypatch, raw):
    FakeConfig.raw = raw
    monkeypatch.setattr(sellers, "DAOAdminConfig", FakeConfig)
    monkeypatch.setattr(sellers, "DAOSellerProfiles", FakeProfiles)
    app = FastAPI()
    app.include_router(sellers.router)
    return TestClient(app).get("/sellers/founding/slots").json()["slots_left"]


def test_founding_slots_follow_the_setting(monkeypatch):
    assert _slots(monkeypatch, {}) == 38                       # default 50
    assert _slots(monkeypatch, {"founding_slots": 60}) == 48   # admin raised it
    assert _slots(monkeypatch, {"founding_slots": 10}) == 0    # never negative
    assert _slots(monkeypatch, {"founding_slots": "abc"}) == 38


class FakeSellerBySlug:
    tier = "founding"

    def read_seller_by_slug_name(self, slug):
        return {"id": "s1", "slug": slug, "tier": self.tier}


def test_tc3_store_page_says_if_founding(monkeypatch):
    monkeypatch.setattr(sellers, "DAOSellerProfiles", FakeSellerBySlug)
    app = FastAPI()
    app.include_router(sellers.router)
    client = TestClient(app)
    for tier, expected in (("founding", True), ("tindahan", False), ("enterprise", False)):
        FakeSellerBySlug.tier = tier
        assert client.get("/sellers/kusina").json()["seller"]["is_founding"] is expected
