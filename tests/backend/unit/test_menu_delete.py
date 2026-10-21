"""TC-4 menu-delete (T87): deleting a dish / price level that was ordered or sits in a
cart. The FKs now SET NULL / CASCADE (migration 20261021020000, checked on DEV by TC-2),
so the DB no longer refuses and both endpoints return 200. No DB, no network.

Run from tests/backend:  pytest unit/test_menu_delete.py
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import apis.sellers as sellers
from core.auth import verify_token

deleted = []


class FakeItems:
    def delete(self, item_id, seller_id):
        deleted.append(("item", item_id, seller_id))
        return [{"id": item_id}]


class FakeVariants:
    def delete(self, variant_id):
        deleted.append(("variant", variant_id))
        return [{"id": variant_id}]


@pytest.fixture
def client(monkeypatch):
    deleted.clear()
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "seller")
    monkeypatch.setattr(sellers, "_assert_owns_variant", lambda variant_id, seller_id: None)
    monkeypatch.setattr(sellers, "DAOFoodItems", FakeItems)
    monkeypatch.setattr(sellers, "DAOFoodItemVariants", FakeVariants)
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "u"}
    return TestClient(app)


def test_delete_dish_and_variant(client):
    assert client.delete("/sellers/me/menu/items/i1").json() == {"success": True}
    assert client.delete("/sellers/me/menu/variants/v1").json() == {"success": True}
    assert deleted == [("item", "i1", "seller"), ("variant", "v1")]
