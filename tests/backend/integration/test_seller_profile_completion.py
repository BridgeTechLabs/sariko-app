"""Existing sellers complete their profile: GET / POST /sellers/me/profile-completion (+ /files),
coming soon without pickup coordinates. Spec docs/dev/seller-profile-completion §6, TC ids in
test names. DAO, storage and auth are faked. No DB, no network.

Run from tests/backend:  pytest integration/test_seller_profile_completion.py
"""
import base64
import copy
import io
import logging
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from apis import cart, seller_profile_completion as spc, sellers
from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig

TODAY = date.today()
VERSION = 20261018
SELLER_A, SELLER_B = "seller-a", "seller-b"
P = "/sellers/me/profile-completion"
USERS = {"user-a": SELLER_A, "user-b": SELLER_B}   # buyer "user-c" has no seller profile


def years_ago(n):
    return TODAY.replace(year=TODAY.year - n) - timedelta(days=1)


def seller(sid, **kw):
    row = {"id": sid, "user_id": next(u for u, s in USERS.items() if s == sid), "store_name": f"Store {sid}",
           "tier": "founding", "phone": None, "address": "1 Le Loi", "lat": None, "lon": None,
           "bank_name": None, "bank_account_number": None, "bank_account_holder": None,
           "status": "active", "slug": sid, "is_open": True, "opening_time": None, "closing_time": None}
    row.update(kw)
    return row


def complete_app(sid, **kw):
    row = {"id": f"app-{sid}", "seller_profile_id": sid, "source": "existing_seller", "status": "submitted",
           "created_at": "2026-10-20T00:00:00+00:00", "full_name": "Nguyễn Văn An",
           "date_of_birth": "1990-01-01", "nationality": "Việt Nam", "id_type": "cccd", "id_number": "079090001234",
           "id_expiry_date": "2035-01-01", "email": "a@x.vn", "residential_address": "2 Hai Ba Trung",
           "tax_code": None, "tax_resident": True, "agreement_version": str(VERSION),
           "personal_data_consent_at": "2026-10-20T00:00:00+00:00", "signature_name": "Nguyễn Văn An"}
    row.update(kw)
    return row


class DB:
    sellers, apps, files, users = {}, {}, [], {}


class FakeDAO:
    def read_seller(self, user_id):
        sid = USERS.get(user_id)
        return copy.deepcopy(DB.sellers.get(sid)) if sid else None

    def read_user_email(self, user_id):
        return DB.users.get(user_id)

    def read_application(self, seller_id):
        rows = [a for a in DB.apps.values() if a.get("seller_profile_id") == seller_id]
        return copy.deepcopy(next((r for r in rows if r["source"] == "existing_seller"), rows[0] if rows else None))

    def count_id_documents(self, application_id):
        return sum(f["application_id"] == application_id and f["kind"] == "id_document" for f in DB.files)

    def create_application(self, data):
        for col in ("full_name", "date_of_birth", "nationality", "id_type", "id_number", "email",
                    "phone", "residential_address", "store_name", "pickup_address", "menu", "tier",
                    "bank_name", "bank_account_number", "bank_account_holder",
                    "agreement_version", "agreed_at", "signature_name"):
            assert data.get(col) is not None, f"not null column {col}"   # mirrors the table
        assert not any(a["source"] == "existing_seller" and a["seller_profile_id"] == data["seller_profile_id"]
                       for a in DB.apps.values()), "unique existing_seller row"
        row = {**data, "id": f"app-new-{len(DB.apps)}", "created_at": "2026-10-20T01:00:00+00:00"}
        DB.apps[row["id"]] = row
        return row

    def update_application(self, application_id, data):
        DB.apps[application_id].update(data)

    def update_seller(self, seller_id, data):
        DB.sellers[seller_id].update(data)

    def create_file(self, data):
        DB.files.append(data)
        return data


class FakeConfig:
    raw = {}

    def get_positive_ints(self, defaults):
        return {k: DAOAdminConfig._positive_int(k, self.raw.get(k), d) for k, d in defaults.items()}


class FakeSupabase:
    """Just enough of the client chain for DAOSellerProfiles' buyer reads: returns only the
    columns the real query selects, so a KYC column added to that select would show up."""
    def table(self, name):
        self.cols = None
        return self

    def select(self, cols):
        self.cols = [c.strip() for c in cols.split(",")]
        return self

    def eq(self, col, value):
        self.slug = value
        return self

    def maybe_single(self):
        return self

    def execute(self):
        row = DB.sellers.get(self.slug)
        return type("R", (), {"data": {c: row.get(c) for c in self.cols} if row else None})()


KYC_FIELDS = ("status", "full_name", "date_of_birth", "id_type", "id_number", "id_expiry_date",
              "residential_address", "tax_resident", "agreement_version", "personal_data_consent_at", "signature_name")
uploads = []


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    DB.sellers = {SELLER_A: seller(SELLER_A), SELLER_B: seller(SELLER_B, phone="+84901111111")}
    DB.apps, DB.files, DB.users = {}, [], {"user-a": "login-a@x.vn", "user-b": "login-b@x.vn"}
    FakeConfig.raw = {"seller_agreement_version": VERSION}
    uploads.clear()
    monkeypatch.setattr(spc, "DAOSellerProfileCompletion", FakeDAO)
    monkeypatch.setattr(spc, "DAOAdminConfig", FakeConfig)
    monkeypatch.setattr(spc, "upload_private", lambda *a: uploads.append(a))
    monkeypatch.setattr(sellers.DAOSellerProfiles, "__init__", lambda self: self.__dict__.update(_supabase_client=FakeSupabase(), _table_name="seller_profiles"))


def client(user_id="user-a"):
    app = FastAPI()
    app.include_router(spc.router)
    app.include_router(sellers.router)
    if user_id:
        app.dependency_overrides[verify_token] = lambda: {"id": user_id}
    return TestClient(app)


def body(**override):
    """Every group, valid, for a Vietnamese seller (cccd)."""
    b = {
        "identity": {"full_name": "Nguyễn Văn An", "date_of_birth": "1990-01-01",
                     "nationality": "Việt Nam", "id_type": "cccd", "id_number": "079090001234",
                     "id_expiry_date": "2035-01-01", "residential_address": "2 Hai Ba Trung"},
        "tax": {"tax_resident": True},
        "bank": {"bank_name": "VCB", "bank_account_number": "0123456789", "bank_account_holder": "NGUYEN VAN AN"},
        "phone": "0901234567",
        "pickup_address": {"address": "1 Le Loi, Q1", "lat": 10.77, "lon": 106.70},
        "agreement": {"agreed": True, "personal_data_consent": True, "agreement_version": VERSION,
                      "signature_name": "Nguyễn Văn An"},
    }
    for k, v in override.items():
        if v is None:
            b.pop(k, None)
        elif isinstance(v, dict) and isinstance(b.get(k), dict):
            b[k] = {**b[k], **v}
        else:
            b[k] = v
    return b


def make_complete(sid=SELLER_A, **app_kw):
    DB.sellers[sid].update(phone="+84901234567", lat=10.77, lon=106.70, bank_name="VCB",
                           bank_account_number="0123456789", bank_account_holder="NGUYEN VAN AN")
    DB.apps[f"app-{sid}"] = complete_app(sid, **app_kw)


def jpg():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


# A. Missing groups
def test_tc01_everything_missing():
    r = client().get(P)
    assert r.status_code == 200
    assert r.json()["complete"] is False
    assert r.json()["missing"] == ["identity", "tax", "bank", "phone", "pickup_address", "agreement"]


def test_tc02_complete():
    make_complete()
    r = client().get(P).json()
    assert r["complete"] is True and r["missing"] == []


@pytest.mark.parametrize("status,complete", [("approved", True), ("draft", False), ("needs_info", False), ("rejected", False)])
def test_tc03_status(status, complete):
    make_complete(status=status)
    r = client().get(P).json()
    assert r["complete"] is complete
    if not complete:
        assert "identity" in r["missing"]


def test_tc04_new_agreement_version():
    make_complete()
    FakeConfig.raw["seller_agreement_version"] = VERSION + 1
    r = client().get(P).json()
    assert r["missing"] == ["agreement"] and r["agreement_version_current"] == VERSION + 1


@pytest.mark.parametrize("field,group", [("bank_account_number", "bank"), ("phone", "phone"),
                                         ("lat", "pickup_address"), ("address", "pickup_address")])
def test_tc05_each_operational_field(field, group):
    make_complete()
    DB.sellers[SELLER_A][field] = None
    assert client().get(P).json()["missing"] == [group]


def test_tc06_id_document_only_for_passport():
    make_complete(id_type="passport", id_number="P1234567")
    assert client().get(P).json()["missing"] == ["id_document"]
    DB.apps[f"app-{SELLER_A}"]["id_type"] = "cccd"
    assert client().get(P).json()["missing"] == []


def test_tc07_prefill():
    DB.sellers[SELLER_A].update(phone="+84901234567", bank_name="VCB", bank_account_number="0123456789")
    p = client().get(P).json()["prefill"]
    assert p["phone"] == "+84901234567" and p["bank_name"] == "VCB" and p["address"] == "1 Le Loi"
    assert p["email"] == "login-a@x.vn"
    assert p["bank_account_number_masked"] == "•••• 6789" and "0123456789" not in str(p)


# B. Saving
def test_tc08_writes_the_right_places():
    r = client().post(P, json=body())
    assert r.status_code == 200, r.text
    assert r.json()["complete"] is True
    s = DB.sellers[SELLER_A]
    assert (s["phone"], s["address"], s["lat"], s["lon"]) == ("+84901234567", "1 Le Loi, Q1", 10.77, 106.70)
    assert (s["bank_name"], s["bank_account_number"], s["bank_account_holder"]) == ("VCB", "0123456789", "NGUYEN VAN AN")
    [app] = DB.apps.values()
    assert app["source"] == "existing_seller" and app["seller_profile_id"] == SELLER_A
    assert app["status"] == "submitted" and app["agreement_version"] == str(VERSION) and app["agreed_at"]
    assert app["personal_data_consent_at"] and app["tier"] == "founding" and app["menu"] == []
    assert app["email"] == "login-a@x.vn" and app["id_expiry_date"] == "2035-01-01"


def test_tc09_resubmit_updates_the_same_row():
    client().post(P, json=body())
    r = client().post(P, json={"phone": "0912345678"})
    assert r.status_code == 200
    assert len(DB.apps) == 1 and DB.sellers[SELLER_A]["phone"] == "+84912345678"
    assert next(iter(DB.apps.values()))["phone"] == "+84912345678"   # row snapshot kept in sync


def test_tc10_only_the_missing_group():
    make_complete()
    DB.sellers[SELLER_A].update(bank_name=None, bank_account_number=None, bank_account_holder=None)
    before = copy.deepcopy(DB.apps)
    r = client().post(P, json={"bank": body()["bank"]})
    assert r.status_code == 200 and r.json()["complete"] is True
    assert DB.sellers[SELLER_A]["bank_account_number"] == "0123456789"
    kyc = lambda apps: {k: {f: a[f] for f in KYC_FIELDS} for k, a in apps.items()}
    assert kyc(DB.apps) == kyc(before)   # identity / tax / agreement untouched


def test_tc11_sign_new_agreement():
    make_complete()
    FakeConfig.raw["seller_agreement_version"] = VERSION + 1
    r = client().post(P, json={"agreement": {**body()["agreement"], "agreement_version": VERSION + 1}})
    assert r.status_code == 200 and r.json()["complete"] is True
    app = DB.apps[f"app-{SELLER_A}"]
    assert app["agreement_version"] == str(VERSION + 1) and app["full_name"] == "Nguyễn Văn An" and app["status"] == "submitted"


def test_missing_group_must_be_sent():
    r = client().post(P, json=body(bank=None))
    assert r.status_code == 400 and r.json()["detail"]["groups"] == ["bank"]
    assert DB.apps == {} and DB.sellers[SELLER_A]["phone"] is None


def _refused(b, status, code):
    before = (copy.deepcopy(DB.sellers), copy.deepcopy(DB.apps))
    r = client().post(P, json=b)
    assert r.status_code == status, r.text
    assert r.json()["detail"]["code"] == code
    assert (DB.sellers, DB.apps) == before   # nothing written


def test_tc12_under_age():
    _refused(body(identity={"date_of_birth": years_ago(17).isoformat()}), 400, "under_age")


@pytest.mark.parametrize("override,status,code", [
    ({"phone": "12345"}, 400, "invalid_phone"),
    ({"agreement": {"signature_name": "Tran Van B"}}, 400, "signature_mismatch"),
    ({"agreement": {"agreed": False}}, 400, "agreement_required"),
    ({"agreement": {"agreement_version": VERSION - 2}}, 409, "agreement_outdated"),
])
def test_tc13_join_rules(override, status, code):
    _refused(body(**override), status, code)


@pytest.mark.parametrize("identity,code", [
    ({"id_number": "07909000123"}, "invalid_id_number"),
    ({"id_type": "passport", "id_number": "P1234567", "id_expiry_date": (TODAY - timedelta(days=1)).isoformat()}, "id_expired"),
    ({"id_type": "passport", "id_number": "P1234567", "id_expiry_date": (TODAY + timedelta(days=90)).isoformat()}, "id_expiring"),
    ({"id_expiry_date": None}, "id_expiry_required"),
])
def test_tc14_id_number_and_expiry(identity, code):
    _refused(body(identity=identity), 400, code)


def test_tc14_cccd_close_to_expiry_is_fine():
    r = client().post(P, json=body(identity={"id_expiry_date": (TODAY + timedelta(days=30)).isoformat()}))
    assert r.status_code == 200


@pytest.mark.parametrize("bank,code", [
    ({"bank_account_number": "12345"}, "invalid_bank_account"),
    ({"bank_account_number": "1" * 21}, "invalid_bank_account"),
    ({"bank_account_holder": "TRAN THI B"}, "bank_holder_mismatch"),
])
def test_tc15_bank(bank, code):
    _refused(body(bank=bank), 400, code)


@pytest.mark.parametrize("holder", ["NGUYEN VAN AN", "nguyễn văn an", "AN NGUYEN VAN"])
def test_tc15_holder_without_accents_matches(holder):
    assert client().post(P, json=body(bank={"bank_account_holder": holder})).status_code == 200


def test_tc16_tax_and_consent():
    _refused(body(tax={"tax_resident": None}), 400, "missing_field")
    _refused(body(agreement={"personal_data_consent": False}), 400, "consent_required")


def test_tc17_location_required():
    _refused(body(pickup_address={"lat": None}), 400, "invalid_location")
    _refused(body(pickup_address={"lat": 123.0}), 400, "invalid_location")


def test_tc18_a_late_check_writes_nothing():
    # the signature check runs after bank / phone / address were read: still nothing written
    _refused(body(agreement={"signature_name": "Someone Else"}), 400, "signature_mismatch")


def test_q12_holder_mismatch_counts_as_missing_bank():
    make_complete()
    DB.sellers[SELLER_A]["bank_account_holder"] = "TRAN THI B"
    assert client().get(P).json()["missing"] == ["bank"]


def test_q13_identity_change_after_approval_goes_back_to_review():
    make_complete(status="approved")
    r = client().post(P, json={"identity": body()["identity"]})
    assert r.status_code == 200 and DB.apps[f"app-{SELLER_A}"]["status"] == "submitted"


def test_q13_agreement_only_keeps_approved():
    make_complete(status="approved")
    FakeConfig.raw["seller_agreement_version"] = VERSION + 1
    client().post(P, json={"agreement": {**body()["agreement"], "agreement_version": VERSION + 1}})
    assert DB.apps[f"app-{SELLER_A}"]["status"] == "approved"


# C. ID document
def _passport_seller():
    client().post(P, json=body(identity={"id_type": "passport", "id_number": "P1234567",
                                          "nationality": "Philippines", "id_expiry_date": "2035-01-01"}))
    assert client().get(P).json()["missing"] == ["id_document"]


def test_tc19_passport_photo():
    _passport_seller()
    r = client().post(P + "/files", json={"kind": "id_document", "file_base64": jpg()})
    assert r.status_code == 200 and r.json()["complete"] is True
    assert len(DB.files) == 1 and uploads[0][0] == "onboarding-files"


def test_tc20_file_limits():
    _passport_seller()
    FakeConfig.raw["onboarding_max_file_mb"] = 1
    big = base64.b64encode(b"\xff\xd8\xff" + b"0" * (1024 * 1024 + 1)).decode()
    for b, code in [({"kind": "id_document", "file_base64": big}, "file_too_large"),
                    ({"kind": "id_document", "file_base64": base64.b64encode(b"GIF89a....").decode()}, "invalid_file_type"),
                    ({"kind": "dish_photo", "file_base64": jpg()}, "invalid_file_kind")]:
        r = client().post(P + "/files", json=b)
        assert r.status_code == 400 and r.json()["detail"]["code"] == code
    FakeConfig.raw["onboarding_max_files_per_kind"] = 1
    assert client().post(P + "/files", json={"kind": "id_document", "file_base64": jpg()}).status_code == 200
    r = client().post(P + "/files", json={"kind": "id_document", "file_base64": jpg()})
    assert r.json()["detail"]["code"] == "too_many_files" and len(DB.files) == 1


def test_tc21_no_cccd_photo():
    client().post(P, json=body())
    r = client().post(P + "/files", json={"kind": "id_document", "file_base64": jpg()})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "id_document_not_needed" and DB.files == []


# D. Access
def test_tc22_no_token():
    c = client(user_id=None)
    for method, path in (("get", P), ("post", P), ("post", P + "/files")):
        r = c.get(path) if method == "get" else c.post(path, json={})
        assert r.status_code in (401, 403)   # HTTPBearer: no header → 403 in FastAPI 0.115


def test_tc23_buyer():
    c = client("user-c")
    assert c.get(P).status_code == 403
    assert c.post(P, json=body()).status_code == 403 and DB.apps == {}


def test_tc24_seller_a_cannot_touch_seller_b():
    b_before = copy.deepcopy(DB.sellers[SELLER_B])
    r = client("user-a").post(P, json={**body(), "seller_id": SELLER_B, "seller_profile_id": SELLER_B,
                                        "application_id": f"app-{SELLER_B}"})
    assert r.status_code == 200
    assert DB.sellers[SELLER_B] == b_before
    assert [a["seller_profile_id"] for a in DB.apps.values()] == [SELLER_A]


# E. KYC data
def test_tc26_public_endpoints_carry_no_kyc():
    client().post(P, json=body())
    r = client().get("/sellers/" + SELLER_A)
    text = r.text
    for value in ("079090001234", "1990-01-01", "2 Hai Ba Trung", "0123456789", "NGUYEN VAN AN"):
        assert value not in text


def test_tc27_masked_prefill_and_keep_on_empty():
    client().post(P, json=body())
    p = client().get(P).json()["prefill"]
    assert p["id_number_masked"] == "•••• 1234" and "079090001234" not in str(p)
    r = client().post(P, json={"identity": {**body()["identity"], "id_number": p["id_number_masked"]},
                                "bank": {**body()["bank"], "bank_account_number": ""}})
    assert r.status_code == 200
    [app] = DB.apps.values()
    assert app["id_number"] == "079090001234" and DB.sellers[SELLER_A]["bank_account_number"] == "0123456789"


def test_tc28_logs_carry_no_numbers(caplog, monkeypatch, tmp_path):
    caplog.set_level(logging.DEBUG)
    monkeypatch.chdir(tmp_path)   # main makes ./logs on import; tests are read-only in CI
    import main   # the app's 422 handler logs validation errors; it must drop the echoed input
    c = client()
    c.app.add_exception_handler(main.RequestValidationError, main.validation_exception_handler)
    # a number where a string is expected: pydantic echoes the value in the error
    assert c.post(P, json={"identity": {"id_number": 79090001234}}).status_code == 422
    assert "79090001234" not in caplog.text
    client().post(P, json=body(phone="bad"))
    client().post(P, json=body())
    client().post(P, json={"identity": {"date_of_birth": "not-a-date", "id_number": "079090001234"}})
    for value in ("079090001234", "0123456789", "1990-01-01"):
        assert value not in caplog.text


def test_tc29_no_storage_path_in_responses():
    _passport_seller()
    r = client().post(P + "/files", json={"kind": "id_document", "file_base64": jpg()})
    assert "onboarding-files" not in r.text and "id_document-" not in r.text
    assert "id_document-" not in client().get(P).text


# F. Coming soon
def test_tc30_tc31_coming_soon_without_coordinates():
    from core.seller_status import with_buyer_status
    s = with_buyer_status({"status": "active", "lat": None, "lon": 106.7})
    assert s["status"] == "coming_soon"
    assert with_buyer_status({"status": "active", "lat": 10.7, "lon": 106.7})["status"] == "active"
    assert with_buyer_status({"status": "coming_soon", "lat": 10.7, "lon": 106.7})["status"] == "coming_soon"
    assert client().get("/sellers/" + SELLER_A).json()["seller"]["status"] == "coming_soon"
    assert DB.sellers[SELLER_A]["status"] == "active"   # DB untouched
    DB.sellers[SELLER_A].update(lat=10.77, lon=106.70)
    assert client().get("/sellers/" + SELLER_A).json()["seller"]["status"] == "active"


class FakeFoodItems:
    gate = {}

    def read_order_gate(self, item_id):
        return self.gate


def test_tc30_cart_refuses_coming_soon(monkeypatch):
    monkeypatch.setattr(cart, "_validate_variant", lambda *a: None)
    monkeypatch.setattr(cart, "DAOFoodItems", FakeFoodItems)
    app = FastAPI()
    app.include_router(cart.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "user-c"}
    FakeFoodItems.gate = {"is_available": True, "preorder_day": 0,
                          "seller_profiles": {"status": "active", "lat": None, "lon": None, "is_open": True}}
    r = TestClient(app).post("/cart/add", json={"seller_id": SELLER_A, "food_item_id": "f1", "quantity": 1})
    assert r.status_code == 400 and "not taking orders" in r.text


def test_tax_resident_also_on_seller_profile():   # tax-withholding TC-14: the withholding rate reads it there
    make_complete(tax_resident=None)
    r = client().post(P, json={"tax": {"tax_resident": False}})
    assert r.status_code == 200, r.text
    assert DB.sellers[SELLER_A]["tax_resident"] is False
    assert DB.apps[f"app-{SELLER_A}"]["tax_resident"] is False


# G. One full name box (docs/dev/seller-full-name N1-N6, TC ids in the names)
def _backfilled_without_middle_name():
    """An older row: first "An" + last "Nguyễn" became full_name "An Nguyễn"; the account says NGUYEN VAN AN."""
    make_complete(full_name="An Nguyễn", status="approved", signature_name="An Nguyễn")


def test_tc8_holder_missing_a_word_shows_the_name_box():
    _backfilled_without_middle_name()
    r = client().get(P).json()
    assert r["missing"] == ["bank"] and r["name_mismatch"] is True and r["prefill"]["full_name"] == "An Nguyễn"


def test_tc8_no_name_box_when_the_holder_matches():
    make_complete()
    assert client().get(P).json()["name_mismatch"] is False
    DB.sellers[SELLER_A]["bank_account_holder"] = None   # empty bank: the bank card, not a name problem
    r = client().get(P).json()
    assert r["missing"] == ["bank"] and r["name_mismatch"] is False


def test_tc8_tc20_fixing_the_name_clears_bank_keeps_the_signature():
    _backfilled_without_middle_name()
    bank = {"bank_name": "VCB", "bank_account_number": "", "bank_account_holder": "NGUYEN VAN AN"}
    r = client().post(P, json={"bank": bank, "full_name": " Nguyễn  Văn An "})
    assert r.status_code == 200, r.text
    assert r.json()["complete"] is True and r.json()["name_mismatch"] is False
    app = DB.apps[f"app-{SELLER_A}"]
    assert app["full_name"] == "Nguyễn Văn An" and app["signature_name"] == "An Nguyễn"   # no new signature
    assert app["status"] == "submitted"   # a changed name goes back to review (Q13)


def test_tc8_the_new_name_must_still_match_the_holder():
    _backfilled_without_middle_name()
    bank = {"bank_name": "VCB", "bank_account_number": "", "bank_account_holder": "NGUYEN VAN AN"}
    _refused({"bank": bank, "full_name": "Trần Thị B"}, 400, "bank_holder_mismatch")
    _refused({"bank": bank, "full_name": "Nguyễn Văn An2"}, 422, "invalid_full_name")


def test_tc8_holder_still_mismatching_without_the_bank_card_is_refused():
    _backfilled_without_middle_name()
    r = client().post(P, json={"full_name": "Nguyễn Văn An"})
    assert r.status_code == 400 and r.json()["detail"]["groups"] == ["bank"]


def test_tc9_full_name_is_the_identity_name():
    make_complete()
    assert client().get(P).json()["missing"] == []
    DB.apps[f"app-{SELLER_A}"]["full_name"] = ""   # backfill of an empty first + last
    assert "identity" in client().get(P).json()["missing"]


def test_tc9_holder_always_checked_against_full_name():
    make_complete()
    DB.sellers[SELLER_A]["bank_account_holder"] = "NGUYEN AN"
    assert client().get(P).json()["missing"] == ["bank"]
    DB.sellers[SELLER_A]["bank_account_holder"] = "AN VAN NGUYEN"   # same words, other order
    assert client().get(P).json()["missing"] == []


def test_tc10_signature_and_holder_by_words_at_save():
    assert client().post(P, json=body(agreement={"signature_name": "An Văn Nguyễn"},
                                      bank={"bank_account_holder": "AN NGUYEN VAN"})).status_code == 200


def test_tc10_missing_middle_name_refused_at_save():
    _refused(body(bank={"bank_account_holder": "NGUYEN AN"}), 400, "bank_holder_mismatch")
    _refused(body(agreement={"signature_name": "Nguyễn An"}), 400, "signature_mismatch")


def test_tc12_old_client_identity_first_last_is_joined():
    identity = {k: v for k, v in body()["identity"].items() if k != "full_name"}
    r = client().post(P, json=body(identity=None) | {"identity": {**identity, "first_name": "An", "last_name": "Nguyễn Văn"}})
    assert r.status_code == 200, r.text
    assert next(iter(DB.apps.values()))["full_name"] == "An Nguyễn Văn"


def test_tc15_identity_name_rules():
    _refused(body(identity={"full_name": "<script>"}), 422, "invalid_full_name")
    _refused(body(identity={"full_name": " "}), 422, "missing_field")


def test_tc21_two_saves_last_name_wins_whole():
    make_complete(status="approved")
    for name in ("Văn An Nguyễn", "Nguyễn Văn An"):
        assert client().post(P, json={"identity": {**body()["identity"], "full_name": name}}).status_code == 200
    app = DB.apps[f"app-{SELLER_A}"]
    assert app["full_name"] == "Nguyễn Văn An" and "first_name" not in app and "last_name" not in app


def test_tc22_name_not_in_logs(caplog, monkeypatch, tmp_path):
    caplog.set_level(logging.DEBUG)
    monkeypatch.chdir(tmp_path)
    import main
    c = client()
    c.app.add_exception_handler(main.RequestValidationError, main.validation_exception_handler)
    c.app.add_exception_handler(main.HTTPException, main.http_exception_handler)
    for b, status in ((body(identity={"full_name": "Zyxwvu " + "x" * 300}), 422), (body(identity={"full_name": "Zyxwvu 1"}), 422),
                      (body(identity={"full_name": "Zyxwvu Qpo"}), 400), ({"full_name": "Zyxwvu Qpo"}, 400)):
        r = c.post(P, json=b)
        assert r.status_code == status and "Zyxwvu" not in r.text
    assert "Zyxwvu" not in caplog.text
