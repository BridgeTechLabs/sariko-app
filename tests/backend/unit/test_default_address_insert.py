"""PATCH /users/me/profile with an address (onboarding, legacy address form) must not hit
the NOT NULL receiver_name/phone_number columns when the user has no address yet."""
from dao.dao_user_addresses import DAOUserAddresses


class _Query:
    """Chainable stand-in for a supabase query; execute() returns what the table is set to give."""
    def __init__(self, db, table):
        self.db, self.table = db, table

    def __getattr__(self, name):
        if name == "insert":
            return lambda data: (self.db.inserts.append(data), self)[1]
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": self.db.rows.get(self.table)})()


class _FakeClient:
    def __init__(self, rows):
        self.rows, self.inserts = rows, []

    def table(self, name):
        return _Query(self, name)


def _dao(rows):
    dao = DAOUserAddresses.__new__(DAOUserAddresses)
    dao._table_name = "user_addresses"
    dao._supabase_client = _FakeClient(rows)
    return dao


def test_new_address_defaults_receiver_to_account_holder():
    dao = _dao({"user_addresses": None, "users": {"name": "Mai", "phone": "+84900000001"}})
    dao.upsert_default_address(user_id="u1", address="12 Nguyễn Huệ")
    (row,) = dao._supabase_client.inserts
    assert row["receiver_name"] == "Mai" and row["phone_number"] == "+84900000001"


def test_new_address_keeps_given_receiver():
    dao = _dao({"user_addresses": None, "users": {"name": "Mai", "phone": "+84900000001"}})
    dao.upsert_default_address(user_id="u1", address="x", receiver_name="Nam", phone_number="+84900000002")
    (row,) = dao._supabase_client.inserts
    assert row["receiver_name"] == "Nam" and row["phone_number"] == "+84900000002"


def test_user_without_name_or_phone_still_inserts():
    dao = _dao({"user_addresses": None, "users": {"name": None, "phone": None}})
    dao.upsert_default_address(user_id="u1", address="x")
    (row,) = dao._supabase_client.inserts
    assert row["receiver_name"] == "" and row["phone_number"] == ""
