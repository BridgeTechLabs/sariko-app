"""T169: a seller edits the store description through PATCH /users/me/profile; GET /sellers/me
returns it so the edit sheet opens with the current text (docs/dev/20261109-store-description)."""
import pytest
from pydantic import ValidationError

from apis import users
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema


@pytest.fixture
def patch_profile(monkeypatch):
    """Calls the handler with fake DAOs; returns what reached seller_profiles and users."""
    def call(is_seller=True, **body):
        written = {"seller": None, "users": None}

        class Sellers:
            def read_seller_profile_by_user_id(self, uid):
                return {"id": "s1"} if is_seller else None

            def update_avatar_url(self, uid, url):
                pass

            def update_seller_profile_info(self, uid, fields):
                written["seller"] = fields

        class Users:
            def update_user_profile(self, uid, data):
                written["users"] = data
                return {"id": uid}

        monkeypatch.setattr(users, "DAOSellerProfiles", Sellers)
        monkeypatch.setattr(users, "DAOUsers", Users)
        users.update_current_user_profile(Schema.RequestUpdateProfile(**body), user={"id": "u1"})
        return written
    return call


def test_description_saved_trimmed(patch_profile):  # TC-11
    assert patch_profile(description="  Home-style Filipino food  ")["seller"] == {"description": "Home-style Filipino food"}


@pytest.mark.parametrize("blank", ["", "   \n "])
def test_blank_description_clears_it(patch_profile, blank):  # TC-11
    assert patch_profile(description=blank)["seller"] == {"description": None}


def test_too_long_rejected_after_trim():  # TC-11
    assert len(Schema.RequestUpdateProfile(description=" " + "x" * 1000 + " ").description) == 1000
    with pytest.raises(ValidationError):
        Schema.RequestUpdateProfile(description="x" * 1001)


def test_other_fields_leave_description_alone(patch_profile):  # TC-11, TC-27
    written = patch_profile(store_name="Rosa Kitchen", phone="0901234567")
    assert "description" not in written["seller"]


def test_buyer_description_ignored(patch_profile):  # TC-27
    written = patch_profile(is_seller=False, name="Ana", description="hi")
    assert written["seller"] is None
    assert written["users"] == {"name": "Ana"}


def test_dao_lets_description_through(monkeypatch):  # TC-12: not in `allowed` = silently dropped, still 200
    sent = {}

    class Query:
        def update(self, fields):
            sent.update(fields)
            return self

        def eq(self, *a):
            return self

        def execute(self):
            return type("R", (), {"data": [sent]})()

    dao = DAOSellerProfiles.__new__(DAOSellerProfiles)
    dao._table_name = "seller_profiles"
    dao._supabase_client = type("C", (), {"table": lambda self, name: Query()})()
    dao.update_seller_profile_info("u1", {"description": None})
    assert sent == {"description": None}


def test_get_seller_info_returns_description(monkeypatch):  # TC-22: read path
    from apis import sellers

    class Sellers:
        def read_seller_profile_by_user_id(self, uid):
            return {"id": "s1", "description": "Cebu-style lechon"}

    monkeypatch.setattr(sellers, "DAOSellerProfiles", Sellers)
    monkeypatch.setattr(sellers, "is_open_now", lambda *a, **k: True)
    assert sellers.get_seller_info(user={"id": "u1"})["description"] == "Cebu-style lechon"
