"""Integration tests for /user_addresses (index, create, update).

The DAO is replaced by an in-memory fake that mirrors the real one's user_id
scoping, so these check the route's rules: auth, ownership, single default,
phone normalization and required-field validation.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis import user_addresses
from core.auth import verify_token

USER_ID = "user-1"
OTHER_USER_ID = "user-2"

VALID_BODY = {
    "address": "1 Le Loi, Q1",
    "receiver_name": "Anh",
    "phone_number": "0901234567",
    "lat": 10.7769,
    "lon": 106.7009,
}
LOCATION = {"address": VALID_BODY["address"], "lat": VALID_BODY["lat"], "lon": VALID_BODY["lon"]}


class _FakeDAO:
    def __init__(self):
        self.rows = []
        self._next_id = 1

    def read_addresses(self, user_id):
        return [r for r in self.rows if r["user_id"] == user_id]

    def read_address(self, user_id, address_id):
        return next((r for r in self.rows if r["user_id"] == user_id and r["id"] == address_id), None)

    def has_address(self, user_id):
        return bool(self.read_addresses(user_id))

    def clear_default(self, user_id, except_id=None):
        for r in self.read_addresses(user_id):
            if r["id"] != except_id:
                r["is_default"] = False

    def create_address(self, user_id, data):
        row = {**data, "user_id": user_id, "id": self._next_id}
        self._next_id += 1
        self.rows.append(row)
        return row

    def update_address(self, user_id, address_id, data):
        row = self.read_address(user_id, address_id)
        if row:
            row.update(data)
        return row


@pytest.fixture
def dao(monkeypatch):
    fake = _FakeDAO()
    monkeypatch.setattr("apis.user_addresses.DAOUserAddresses", lambda: fake)
    return fake


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(user_addresses.router)
    app.dependency_overrides[verify_token] = lambda: {"id": USER_ID}
    return TestClient(app)


def _defaults(dao, user_id=USER_ID):
    return [r["id"] for r in dao.read_addresses(user_id) if r["is_default"]]


def test_requires_auth():
    app = FastAPI()
    app.include_router(user_addresses.router)
    res = TestClient(app).get("/user_addresses")
    assert res.status_code == 403


def test_index_only_returns_own_addresses(client, dao):
    dao.create_address(OTHER_USER_ID, {**VALID_BODY, "is_default": True})
    client.post("/user_addresses", json=VALID_BODY)

    res = client.get("/user_addresses")

    assert res.status_code == 200
    assert [a["user_id"] for a in res.json()["addresses"]] == [USER_ID]


def test_create_ignores_user_id_in_body(client, dao):
    res = client.post("/user_addresses", json={**VALID_BODY, "user_id": OTHER_USER_ID})

    assert res.status_code == 200
    assert res.json()["address"]["user_id"] == USER_ID


def test_create_first_address_becomes_default(client, dao):
    res = client.post("/user_addresses", json={**VALID_BODY, "is_default": False})

    assert res.json()["address"]["is_default"] is True


def test_create_default_clears_previous_default(client, dao):
    first = client.post("/user_addresses", json=VALID_BODY).json()["address"]
    second = client.post("/user_addresses", json={**VALID_BODY, "is_default": True}).json()["address"]

    assert _defaults(dao) == [second["id"]]
    assert first["id"] != second["id"]


def test_create_normalizes_phone(client, dao):
    res = client.post("/user_addresses", json=VALID_BODY)

    assert res.json()["address"]["phone_number"] == "+84901234567"


def test_create_rejects_invalid_phone(client, dao):
    res = client.post("/user_addresses", json={**VALID_BODY, "phone_number": "123"})

    assert res.status_code == 422


@pytest.mark.parametrize("field", ["address", "receiver_name", "phone_number", "lat", "lon"])
def test_create_requires_field(client, dao, field):
    body = {k: v for k, v in VALID_BODY.items() if k != field}

    assert client.post("/user_addresses", json=body).status_code == 422
    assert client.post("/user_addresses", json={**VALID_BODY, field: ""}).status_code == 422


def test_street_name_is_optional_and_saved(client, dao):
    created = client.post("/user_addresses", json=VALID_BODY).json()["address"]
    assert "street_name" not in created or created["street_name"] is None

    res = client.patch(f"/user_addresses/{created['id']}", json={**LOCATION, "street_name": "Le Loi"})

    assert res.json()["address"]["street_name"] == "Le Loi"


def test_update_partial_and_clear_note(client, dao):
    created = client.post("/user_addresses", json={**VALID_BODY, "note": "gate 2"}).json()["address"]

    res = client.patch(f"/user_addresses/{created['id']}", json={**LOCATION, "receiver_name": "Binh", "note": None})

    address = res.json()["address"]
    assert res.status_code == 200
    assert address["receiver_name"] == "Binh"
    assert address["note"] is None
    assert address["address"] == VALID_BODY["address"]


@pytest.mark.parametrize("field", ["address", "receiver_name", "phone_number", "lat", "lon", "is_default"])
def test_update_rejects_null_required(client, dao, field):
    created = client.post("/user_addresses", json=VALID_BODY).json()["address"]

    res = client.patch(f"/user_addresses/{created['id']}", json={**LOCATION, field: None})

    assert res.status_code == 422


@pytest.mark.parametrize("field", ["address", "lat", "lon"])
def test_update_requires_location(client, dao, field):
    created = client.post("/user_addresses", json=VALID_BODY).json()["address"]
    body = {k: v for k, v in LOCATION.items() if k != field}

    res = client.patch(f"/user_addresses/{created['id']}", json={**body, "receiver_name": "Binh"})

    assert res.status_code == 422


def test_update_set_default_moves_default(client, dao):
    client.post("/user_addresses", json=VALID_BODY)
    second = client.post("/user_addresses", json=VALID_BODY).json()["address"]

    client.patch(f"/user_addresses/{second['id']}", json={**LOCATION, "is_default": True})

    assert _defaults(dao) == [second["id"]]


def test_update_cannot_unset_default(client, dao):
    created = client.post("/user_addresses", json=VALID_BODY).json()["address"]

    res = client.patch(f"/user_addresses/{created['id']}", json={**LOCATION, "is_default": False})

    assert res.status_code == 400
    assert _defaults(dao) == [created["id"]]


def test_update_other_users_address_is_404(client, dao):
    other = dao.create_address(OTHER_USER_ID, {**VALID_BODY, "is_default": True})

    res = client.patch(f"/user_addresses/{other['id']}", json={**LOCATION, "receiver_name": "Hacker"})

    assert res.status_code == 404
    assert other["receiver_name"] == VALID_BODY["receiver_name"]
