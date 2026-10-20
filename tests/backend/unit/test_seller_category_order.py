"""P1-5: reordering categories writes sort_order through PATCH /me/menu/categories/{id},
which only ever touches the caller's own categories."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token
from dao.dao_menu_categories import DAOMenuCategories


def test_other_sellers_category_is_404(monkeypatch):  # TC-23
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-b"}
    monkeypatch.setattr("apis.sellers._get_seller_id", lambda user: "seller-b")
    seen = {}

    class FakeCategories:
        def update(self, cat_id, seller_id, fields):
            seen.update(cat_id=cat_id, seller_id=seller_id, fields=fields)
            return None   # no row of seller-b has this id

    monkeypatch.setattr("apis.sellers.DAOMenuCategories", FakeCategories)
    res = TestClient(app).patch("/sellers/me/menu/categories/cat-of-a", json={"sort_order": 2})
    assert res.status_code == 404
    assert seen == {"cat_id": "cat-of-a", "seller_id": "seller-b", "fields": {"sort_order": 2}}


def test_update_filters_on_seller():  # TC-23
    calls = []

    class Q:
        data = []

        def __getattr__(self, name):
            def record(*args):
                calls.append((name, args))
                return self
            return record

        def execute(self):
            return self

    dao = DAOMenuCategories.__new__(DAOMenuCategories)
    dao._table_name = "menu_categories"
    dao._supabase_client = type("C", (), {"table": lambda self, t: Q()})()
    assert dao.update("cat-of-a", "seller-b", {"sort_order": 2}) is None
    assert ("eq", ("id", "cat-of-a")) in calls
    assert ("eq", ("seller_id", "seller-b")) in calls
