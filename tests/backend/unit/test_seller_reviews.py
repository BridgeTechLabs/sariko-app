"""P1-2: seller reviews — only sellers get in, the rating summary comes with GET /me,
and the list stays masked and scoped to the caller's own store."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import sellers
from core.auth import verify_token


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-1"}
    return TestClient(app)


def _profiles(monkeypatch, profile):
    monkeypatch.setattr("apis.sellers.DAOSellerProfiles",
                        lambda: type("P", (), {"read_seller_profile_by_user_id": lambda self, uid: profile})())


def test_buyer_gets_403(client, monkeypatch):  # TC-1
    _profiles(monkeypatch, None)
    res = client.get("/sellers/me/reviews")
    assert res.status_code == 403
    assert res.json()["detail"] == "User is not a seller"


@pytest.mark.parametrize("avg, count, want_avg, want_count", [(4.5, 2, 4.5, 2), (None, 0, None, 0)])
def test_me_returns_rating(client, monkeypatch, avg, count, want_avg, want_count):  # TC-2
    _profiles(monkeypatch, {"id": "seller-1", "rating_avg": avg, "rating_count": count})
    body = client.get("/sellers/me").json()
    assert body["rating_avg"] == want_avg
    assert body["rating_count"] == want_count


def test_reviews_masked_and_scoped(client, monkeypatch):  # TC-3
    _profiles(monkeypatch, {"id": "seller-1"})
    asked = {}

    class FakeReviews:
        def read_reviews_by_seller_id(self, seller_id, limit, offset):
            asked.update(seller_id=seller_id, limit=limit, offset=offset)
            return [
                {"id": "r1", "rating": 5, "comment": "Fast", "items": [],
                 "users": {"name": "Maria Santos", "avatar_url": None}},
                {"id": "r2", "rating": 4, "comment": None,
                 "items": [{"food_item_id": None, "name_snapshot": "Adobo", "rating": 3}],
                 "users": {"name": "Juan Cruz", "avatar_url": "a.png"}},
            ]

    monkeypatch.setattr("apis.sellers.DAOReviews", FakeReviews)
    res = client.get("/sellers/me/reviews?limit=10&offset=10")
    assert res.status_code == 200
    assert asked == {"seller_id": "seller-1", "limit": 10, "offset": 10}

    first, second = res.json()["reviews"]
    assert first["comment"] == "Fast"
    assert second["items"] == [{"food_item_id": None, "name_snapshot": "Adobo", "rating": 3}]
    for row in (first, second):
        assert "users" not in row
    assert first["reviewer_name"] != "Maria Santos"
    assert second["reviewer_name"] != "Juan Cruz"
    assert second["reviewer_avatar_url"] == "a.png"
