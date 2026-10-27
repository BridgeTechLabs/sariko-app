"""menu-delete group B, R-1..R-15: reviews live in review_stores (one per order) and
review_items (optional dishes). The real DAOReviews runs against an in-memory stand-in for
the Supabase client that enforces the two unique keys, so 409 / all-or-nothing are checked
end to end. No DB, no network.

Run from tests/backend:  pytest unit/test_reviews_two_tables.py
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

import apis.reviews as reviews
import apis.sellers as sellers
import dao.dao_orders as dao_orders_module
from core.auth import verify_token
from dao.dao_reviews import DAOReviews

UNIQUE = {"review_stores": ("order_id",), "review_items": ("order_id", "food_item_id")}


class FakeDB:
    def __init__(self):
        self.tables = {"review_stores": [], "review_items": []}
        self.fail_insert = set()   # table names whose next insert raises
        self.next_id = 0

    def table(self, name):
        return _Query(self, name)


class _Query:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.op, self.payload, self.filters = "select", None, []
        self.desc, self.window = False, None

    def select(self, *_):
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        self.filters.append(lambda r: r.get(col) in vals)
        return self

    def order(self, col, desc=False):
        self.desc = desc
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def execute(self):
        rows = self.db.tables[self.name]
        if self.op == "insert":
            if self.name in self.db.fail_insert:
                raise APIError({"code": "XX000", "message": "boom"})
            new = self.payload if isinstance(self.payload, list) else [self.payload]
            keys = UNIQUE[self.name]
            seen = {tuple(r[k] for k in keys) for r in rows}
            for r in new:
                key = tuple(r[k] for k in keys)
                if None not in key and key in seen:
                    raise APIError({"code": "23505", "message": "duplicate"})
                seen.add(key)
            out = []
            for r in new:
                self.db.next_id += 1
                out.append({**r, "id": f"{self.name}-{self.db.next_id}", "created_at": self.db.next_id})
            rows.extend(out)
            return type("R", (), {"data": out})()
        match = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "delete":
            self.db.tables[self.name] = [r for r in rows if r not in match]
            return type("R", (), {"data": match})()
        match = sorted(match, key=lambda r: r["created_at"], reverse=self.desc)
        if self.window:
            match = match[self.window[0]:self.window[1] + 1]
        return type("R", (), {"data": [{**r, "users": None} for r in match]})()


ORDERS = {
    "o1": {"id": "o1", "user_id": "buyer", "seller_id": "s1", "status": "done", "payment_status": "paid",
           "order_items": [{"food_item_id": "adobo", "name_snapshot": "Adobo"},
                           {"food_item_id": "flan", "name_snapshot": "Leche Flan"},
                           {"food_item_id": None, "name_snapshot": "Gone dish"}]},
    "o2": {"id": "o2", "user_id": "buyer", "seller_id": "s1", "status": "delivering", "payment_status": "paid",
           "order_items": []},
    "o3": {"id": "o3", "user_id": "buyer", "seller_id": "s1", "status": "done", "payment_status": "pending",
           "order_items": []},
    "o4": {"id": "o4", "user_id": "buyer", "seller_id": "s2", "status": "done", "payment_status": "paid",
           "order_items": [{"food_item_id": "adobo", "name_snapshot": "Adobo"}]},
}


class FakeOrders:
    def read_order_by_id(self, order_id, user_id):
        order = ORDERS.get(order_id)
        return order if order and order["user_id"] == user_id else None


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(DAOReviews, "__init__", lambda self: setattr(self, "_supabase_client", fake))
    monkeypatch.setattr(reviews, "DAOOrders", FakeOrders)
    return fake


def _client(user_id):
    app = FastAPI()
    app.include_router(reviews.router)
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": user_id}
    return TestClient(app)


@pytest.fixture
def buyer(db):
    return _client("buyer")


def test_r1_store_only(buyer, db):
    res = buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 4})
    assert res.status_code == 200
    assert [(r["rating"], r["comment"]) for r in db.tables["review_stores"]] == [(4, None)]
    assert db.tables["review_items"] == []


def test_r2_store_comment_and_two_dishes(buyer, db):
    res = buyer.post("/reviews", json={
        "order_id": "o1", "overall_rating": 5, "overall_comment": "Fast and hot",
        "items": [{"food_item_id": "adobo", "rating": 4, "comment": "Salty"},
                  {"food_item_id": "flan", "rating": 5}]})
    assert res.status_code == 200
    assert db.tables["review_stores"][0]["comment"] == "Fast and hot"
    assert [(i["name_snapshot"], i["comment"], i["seller_id"]) for i in db.tables["review_items"]] == [
        ("Adobo", "Salty", "s1"), ("Leche Flan", None, "s1")]


@pytest.mark.parametrize("body", [
    {"order_id": "o1"},
    {"order_id": "o1", "overall_rating": 0},
    {"order_id": "o1", "overall_rating": 6},
    {"order_id": "o1", "overall_rating": 5, "items": [{"food_item_id": "adobo", "rating": 0}]},
    {"order_id": "o1", "overall_rating": 5, "items": [{"food_item_id": "adobo", "rating": 6}]},
    {"order_id": "o1", "overall_rating": 5, "overall_comment": "x" * 501},                     # R-4
    {"order_id": "o1", "overall_rating": 5, "items": [{"food_item_id": "adobo", "rating": 5, "comment": "x" * 501}]},
    {"order_id": "o1", "overall_rating": 5, "items": [{"food_item_id": "adobo", "rating": 5},  # R-5
                                                      {"food_item_id": "adobo", "rating": 4}]},
])
def test_r3_r4_r5_validation_422(buyer, db, body):
    assert buyer.post("/reviews", json=body).status_code == 422
    assert db.tables == {"review_stores": [], "review_items": []}


@pytest.mark.parametrize("order_id, items, code", [
    ("o1", [{"food_item_id": "sisig", "rating": 5}], 400),   # R-6 dish not on the order
    ("nope", [], 404),                                        # R-7 no such order
    ("o2", [], 400),                                          # R-8 not done
    ("o3", [], 400),                                          # R-8 done, not paid
])
def test_r6_r7_r8_refused(buyer, db, order_id, items, code):
    res = buyer.post("/reviews", json={"order_id": order_id, "overall_rating": 5, "items": items})
    assert res.status_code == code
    assert db.tables == {"review_stores": [], "review_items": []}


def test_r7_someone_elses_order_404(db):
    res = _client("stranger").post("/reviews", json={"order_id": "o1", "overall_rating": 5})
    assert res.status_code == 404


def test_r9_second_submit_409_adds_nothing(buyer, db):
    body = {"order_id": "o1", "overall_rating": 5, "items": [{"food_item_id": "adobo", "rating": 5}]}
    assert buyer.post("/reviews", json=body).status_code == 200
    assert buyer.post("/reviews", json=body).status_code == 409
    assert (len(db.tables["review_stores"]), len(db.tables["review_items"])) == (1, 1)


def test_r10_items_insert_fails_no_lone_store_row(buyer, db):
    db.fail_insert.add("review_items")
    with pytest.raises(Exception):
        buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 5,
                                     "items": [{"food_item_id": "adobo", "rating": 5}]})
    assert db.tables == {"review_stores": [], "review_items": []}
    db.fail_insert.clear()
    assert buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 5}).status_code == 200


def test_r11_r12_get_order_review(buyer, db):
    assert buyer.get("/reviews/orders/o1").json() == {
        "success": True, "reviewed": False, "overall_rating": None, "overall_comment": None, "items": []}

    buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 4, "overall_comment": "Good",
                                 "items": [{"food_item_id": "adobo", "rating": 3}]})
    body = buyer.get("/reviews/orders/o1").json()
    assert (body["reviewed"], body["overall_rating"], body["overall_comment"]) == (True, 4, "Good")
    assert [(i["food_item_id"], i["name_snapshot"]) for i in body["items"]] == [("adobo", "Adobo")]

    # R-12: the dish is deleted (ON DELETE SET NULL); the review stays under its name.
    db.tables["review_items"][0]["food_item_id"] = None
    assert [(i["food_item_id"], i["name_snapshot"]) for i in buyer.get("/reviews/orders/o1").json()["items"]] == [
        (None, "Adobo")]

    # R-11: another user sees nothing of it.
    assert _client("stranger").get("/reviews/orders/o1").json()["reviewed"] is False


def test_r13_food_reviews_newest_first_and_paged(buyer, db):
    buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 5,
                                 "items": [{"food_item_id": "adobo", "rating": 2}, {"food_item_id": "flan", "rating": 5}]})
    buyer.post("/reviews", json={"order_id": "o4", "overall_rating": 5,
                                 "items": [{"food_item_id": "adobo", "rating": 4}]})
    ratings = lambda q: [r["rating"] for r in buyer.get(f"/reviews/food/adobo{q}").json()["reviews"]]
    assert ratings("") == [4, 2]
    assert ratings("?limit=1&offset=1") == [2]
    assert buyer.get("/reviews/food/sisig").json() == {"success": True, "reviews": []}
    assert all("users" not in r for r in buyer.get("/reviews/food/adobo").json()["reviews"])


def test_r14_seller_sees_own_store_with_dishes(buyer, db, monkeypatch):
    buyer.post("/reviews", json={"order_id": "o1", "overall_rating": 4, "overall_comment": "Nice",
                                 "items": [{"food_item_id": "adobo", "rating": 3}]})
    buyer.post("/reviews", json={"order_id": "o4", "overall_rating": 1})
    db.tables["review_items"][0]["food_item_id"] = None          # dish since deleted
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "s1")

    rows = _client("seller-user").get("/sellers/me/reviews").json()["reviews"]
    assert [(r["rating"], r["comment"]) for r in rows] == [(4, "Nice")]
    assert [(i["food_item_id"], i["name_snapshot"], i["rating"]) for i in rows[0]["items"]] == [(None, "Adobo", 3)]


def test_r15_orders_list_embeds_review_stores():
    # OrderCard reads order.review_stores: a to-one embed (order_id is unique), null until reviewed.
    import inspect
    src = inspect.getsource(dao_orders_module.DAOOrders.read_orders_by_user_id)
    assert "review_stores(id)" in src and "reviews(id)" not in src
