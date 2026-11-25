"""Admin gateway seller KYC (docs/dev/20261124-seller-kyc-admin, TC ids in test names): an operator fills in a seller's
ID / tax / bank and passport photos with the seller form's own checks; the application status never changes and
nothing signs the agreement. DAO, storage and settings are faked; no DB, no network."""
import base64
import copy
import io
import logging
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from apis import admin_gateway as gw, seller_profile_completion as spc
from dao.dao_admin_config import DAOAdminConfig

KEY = "gw_test_key_0123456789"
SID, OTHER = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
VERSION = 20261023
TODAY = date.today()
P = f"/rest/v1/admin-gateway/sellers/{SID}/kyc"
# Columns the table keeps NOT NULL after 20261124200000 (the other 8 only for source 'join').
NOT_NULL = ("full_name", "date_of_birth", "nationality", "id_type", "id_number", "email", "residential_address",
            "store_name", "menu", "tier", "source", "status")
JOIN_ONLY = ("agreement_version", "agreed_at", "signature_name", "bank_name", "bank_account_number",
             "bank_account_holder", "phone", "pickup_address")


def seller(sid, **kw):
    row = {"id": sid, "user_id": f"user-{sid}", "store_name": "Bếp Maria", "tier": "founding", "phone": None,
           "address": "1 Le Loi", "lat": 10.7, "lon": 106.7, "bank_name": None, "bank_account_number": None,
           "bank_account_holder": None, "tax_resident": True}
    row.update(kw)
    return row


def application(sid, **kw):
    row = {"id": f"app-{sid}", "seller_profile_id": sid, "source": "existing_seller", "status": "approved",
           "created_at": "2026-10-20T00:00:00+00:00", "full_name": "Maria Santos Reyes", "date_of_birth": "1990-01-01",
           "nationality": "Philippines", "id_type": "passport", "id_number": "P1234567", "id_expiry_date": "2035-01-01",
           "email": "maria@x.ph", "residential_address": "2 Hai Ba Trung", "tax_code": None, "tax_resident": True,
           "agreement_version": str(VERSION), "agreed_at": "2026-10-20T00:00:00+00:00",
           "personal_data_consent_at": "2026-10-20T00:00:00+00:00", "signature_name": "Maria Santos Reyes",
           "phone": "+84901234567", "pickup_address": "1 Le Loi", "bank_name": "VCB",
           "bank_account_number": "0123456789", "bank_account_holder": "MARIA SANTOS REYES",
           "store_name": "Bếp Maria", "tier": "founding", "menu": []}
    row.update(kw)
    return row


class DB:
    sellers, apps, files, objects, writes = {}, {}, [], set(), []


class FakeDAO:
    def read_seller(self, value, column="user_id"):
        assert column == "id"
        return copy.deepcopy(DB.sellers.get(value))

    def read_user_email(self, user_id):
        return "login@x.vn"

    def read_application(self, seller_id):
        rows = [a for a in DB.apps.values() if a["seller_profile_id"] == seller_id]
        return copy.deepcopy(next((r for r in rows if r["source"] == "existing_seller"), rows[0] if rows else None))

    def list_id_documents(self, application_id):
        return [dict(f) for f in DB.files if f["application_id"] == application_id and f["kind"] == "id_document"]

    def count_id_documents(self, application_id):
        return len(self.list_id_documents(application_id))

    def _check(self, row):
        for col in NOT_NULL + (JOIN_ONLY if row["source"] == "join" else ()):
            assert row.get(col) is not None, f"not null column {col}"   # mirrors the table + its CHECK

    def create_application(self, data):
        DB.writes.append(("create_application", data))
        row = {**data, "id": f"app-new-{len(DB.apps)}", "created_at": "2026-11-24T00:00:00+00:00"}
        self._check(row)
        DB.apps[row["id"]] = row
        return row

    def update_application(self, application_id, data):
        DB.writes.append(("update_application", data))
        self._check({**DB.apps[application_id], **data})
        DB.apps[application_id].update(data)

    def update_seller(self, seller_id, data):
        DB.writes.append(("update_seller", data))
        DB.sellers[seller_id].update(data)

    def create_file(self, data):
        row = {**data, "id": f"33333333-3333-4333-8333-33333333333{len(DB.files)}"}
        DB.files.append(row)
        return row

    def delete_file(self, file_id):
        DB.files[:] = [f for f in DB.files if f["id"] != file_id]


class FakeConfig:
    def get_positive_ints(self, defaults):
        raw = {"seller_agreement_version": VERSION}
        return {k: DAOAdminConfig._positive_int(k, raw.get(k), d) for k, d in defaults.items()}


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    DB.sellers = {SID: seller(SID), OTHER: seller(OTHER)}
    DB.apps, DB.files, DB.objects, DB.writes = {}, [], set(), []
    monkeypatch.setenv("ADMIN_GATEWAY_API_KEY", KEY)
    monkeypatch.setattr(gw, "DAOSellerProfileCompletion", FakeDAO)
    monkeypatch.setattr(spc, "DAOAdminConfig", FakeConfig)
    monkeypatch.setattr(spc, "upload_private", lambda bucket, path, *a: DB.objects.add(path))
    monkeypatch.setattr(gw, "remove_private", lambda bucket, path: DB.objects.discard(path))
    monkeypatch.setattr(gw, "signed_url", lambda bucket, path, seconds: f"https://signed/{path}?s={seconds}")


app = FastAPI()
app.include_router(gw.router, prefix="/rest/v1")
api = TestClient(app, headers={"X-Api-Key": KEY})


def with_app(**kw):
    DB.sellers[SID].update(phone="+84901234567", bank_name="VCB", bank_account_number="0123456789",
                           bank_account_holder="MARIA SANTOS REYES")
    DB.apps[f"app-{SID}"] = application(SID, **kw)
    return DB.apps[f"app-{SID}"]


def identity(**kw):
    i = {"full_name": "Maria Santos Reyes", "date_of_birth": "1990-01-01", "nationality": "Philippines",
         "id_type": "passport", "id_number": "P1234567", "id_expiry_date": "2035-01-01",
         "residential_address": "2 Hai Ba Trung"}
    i.update(kw)
    return {"identity": i}


def bank(**kw):
    return {"bank": {"bank_name": "VCB", "bank_account_number": "0123456789",
                     "bank_account_holder": "MARIA SANTOS REYES", **kw}}


def photo(mb=0):
    if mb:
        return base64.b64encode(b"\xff\xd8\xff" + b"0" * (mb * 1024 * 1024)).decode()
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def upload(data=None):
    return api.post(f"{P}/files", json={"kind": "id_document", "file_base64": data or photo()})


def code(res):
    return res.json()["detail"]["code"]


def seller_missing():
    """What the seller's app then reports as missing (the seller form's own rule)."""
    a = FakeDAO().read_application(SID)
    return spc.missing_groups(DB.sellers[SID], a, FakeDAO().count_id_documents(a["id"]) if a else 0, VERSION)


@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "wrong"}])
def test_tc01_bad_or_missing_key_is_401(headers):
    for method, path in (("get", P), ("put", P), ("post", f"{P}/files"), ("delete", f"{P}/files/{OTHER}")):
        res = getattr(TestClient(app), method)(path, headers=headers)
        assert res.status_code == 401, (method, path)
    assert DB.writes == []


def test_tc02_get_full_numbers_tax_from_seller_profile_agreement_photos_limits():
    with_app(tax_resident=True)
    DB.sellers[SID]["tax_resident"] = False
    DB.files.append({"id": "f1", "application_id": f"app-{SID}", "kind": "id_document", "storage_path": "p/1.jpg",
                     "content_type": "image/jpeg"})
    r = api.get(P).json()
    assert r["status"] == "approved"
    assert r["identity"]["id_number"] == "P1234567" and r["identity"]["email"] == "maria@x.ph"
    assert r["bank"]["bank_account_number"] == "0123456789"
    assert r["tax"]["tax_resident"] is False
    assert r["agreement"] == {"agreement_version": str(VERSION), "agreed_at": "2026-10-20T00:00:00+00:00",
                              "signature_name": "Maria Santos Reyes",
                              "personal_data_consent_at": "2026-10-20T00:00:00+00:00", "version_current": VERSION}
    assert r["id_documents"] == [{"id": "f1", "content_type": "image/jpeg", "url": "https://signed/p/1.jpg?s=600"}]
    assert r["limits"] == {"min_age": 18, "min_id_validity_months": 6, "max_file_mb": 5, "max_files_per_kind": 2}


def test_tc02_get_without_application_and_unknown_seller():
    r = api.get(P).json()
    assert r["status"] is None and r["identity"]["full_name"] is None and r["identity"]["email"] == "login@x.vn"
    assert r["id_documents"] == [] and r["agreement"]["agreement_version"] is None
    assert api.get("/rest/v1/admin-gateway/sellers/44444444-4444-4444-8444-444444444444/kyc").status_code == 404


def test_tc03_name_change_keeps_approved():
    with_app(bank_account_holder="REYES MARIA SANTOS")
    DB.sellers[SID]["bank_account_holder"] = "REYES MARIA SANTOS"
    r = api.put(P, json=identity(full_name="Maria Santos Reyes", id_expiry_date="2035-01-01"))
    assert r.status_code == 200 and r.json()["changed"] == []
    DB.sellers[SID]["bank_account_holder"] = "MARIA REYES SANTOS"
    r = api.put(P, json=identity(full_name="Maria Reyes Santos"))
    assert r.status_code == 200, r.json()
    assert r.json()["changed"] == ["full_name"] and r.json()["status"] == "approved"
    assert DB.apps[f"app-{SID}"]["status"] == "approved"


@pytest.mark.parametrize("status", ["submitted", "needs_info", "rejected"])
def test_tc04_tc21_status_kept(status):
    with_app(status=status)
    r = api.put(P, json=identity(residential_address="9 Nguyen Hue"))
    assert r.status_code == 200 and r.json()["status"] == status
    assert DB.apps[f"app-{SID}"]["residential_address"] == "9 Nguyen Hue"
    if status != "submitted":   # TC-21: the seller is still told to fix ID until reviewed / resent
        assert "identity" in seller_missing()


def test_tc05_new_application_is_approved_with_snapshot():
    DB.sellers[SID].update(phone="+84901234567", bank_name="VCB", bank_account_number="0123456789",
                           bank_account_holder="MARIA SANTOS REYES")
    r = api.put(P, json=identity())
    assert r.status_code == 200 and r.json()["status"] == "approved"
    (row,) = DB.apps.values()
    assert row["source"] == "existing_seller" and row["seller_profile_id"] == SID and row["reviewed_at"]
    assert (row["phone"], row["bank_account_number"], row["store_name"], row["tier"], row["email"]) == (
        "+84901234567", "0123456789", "Bếp Maria", "founding", "login@x.vn")
    assert "full_name" in r.json()["changed"]


def test_tc19_new_application_without_bank_phone_or_agreement():
    r = api.put(P, json=identity())
    assert r.status_code == 200
    (row,) = DB.apps.values()
    for col in ("agreement_version", "agreed_at", "signature_name", "personal_data_consent_at",
                "bank_name", "bank_account_number", "bank_account_holder", "phone"):
        assert row.get(col) is None, col   # never a made-up value: only the seller signs
    missing = seller_missing()
    assert {"agreement", "bank", "phone", "id_document"} <= set(missing) and "identity" not in missing


@pytest.mark.parametrize("change,err", [
    ({"id_type": "cccd", "id_number": "07909000123"}, "invalid_id_number"),
    ({"id_expiry_date": (TODAY + timedelta(days=150)).isoformat()}, "id_expiring"),
    ({"date_of_birth": (TODAY.replace(year=TODAY.year - 17)).isoformat()}, "under_age"),
    ({"residential_address": "  "}, "missing_field"),
])
def test_tc06_same_codes_as_the_seller_form_nothing_written(change, err):
    with_app()
    r = api.put(P, json=identity(**change))
    assert r.status_code == 400 and code(r) == err and DB.writes == []


def test_tc07_name_change_against_other_holder():
    with_app()
    DB.sellers[SID]["bank_account_holder"] = "NGUYEN VAN AN"
    DB.apps[f"app-{SID}"]["full_name"] = "Nguyễn Văn An"
    r = api.put(P, json=identity(full_name="Trần Thị Bình"))
    assert r.status_code == 400 and code(r) == "bank_holder_mismatch" and DB.writes == []


def test_tc22_holder_already_off_other_fields_still_save():
    with_app()
    DB.sellers[SID]["bank_account_holder"] = "MARIA REYES"
    r = api.put(P, json=identity(id_expiry_date="2036-01-01"))
    assert r.status_code == 200 and r.json()["changed"] == ["id_expiry_date"]


def test_tc22_first_save_with_a_holder_already_off_then_bank_fixed():
    """QĐ-4 (spec e4dbb73): no earlier name = no holder check on the identity save, else the seller is stuck."""
    DB.sellers[SID]["bank_account_holder"] = "MARIA REYES"
    assert api.put(P, json=identity(full_name="Maria Santos Reyes")).status_code == 200
    assert api.put(P, json=bank(bank_account_holder="MARIA SANTOS REYES")).status_code == 200
    assert DB.sellers[SID]["bank_account_holder"] == "MARIA SANTOS REYES"


def test_tc22_case_or_spacing_of_the_same_name_is_no_change():
    with_app()
    DB.sellers[SID]["bank_account_holder"] = "MARIA REYES"
    assert api.put(P, json=identity(full_name="maria  santos REYES")).status_code == 200


def test_tc08_tax_both_places():
    with_app()
    r = api.put(P, json={"tax": {"tax_resident": False, "tax_code": " 0312345678 "}})   # develop: MST required, 10 or 13 digits
    assert r.status_code == 200 and r.json()["changed"] == ["tax_code", "tax_resident"]
    assert DB.apps[f"app-{SID}"]["tax_resident"] is False and DB.apps[f"app-{SID}"]["tax_code"] == "0312345678"
    assert DB.sellers[SID]["tax_resident"] is False and r.json()["tax"]["tax_resident"] is False
    r = api.put(P, json={"tax": {"tax_resident": None}})
    assert r.status_code == 400 and code(r) == "missing_field"


@pytest.mark.parametrize("extra", [
    {"agreement": {"agreed": True, "personal_data_consent": True, "agreement_version": VERSION, "signature_name": "X"}},
    {"phone": "0901234567"}, {"pickup_address": {"address": "x", "lat": 1, "lon": 1}}, {},
])
def test_tc09_only_identity_tax_bank(extra):
    with_app()
    r = api.put(P, json={**identity(), **extra})
    if extra:
        assert r.status_code == 422 and DB.writes == []
    else:
        assert api.put(P, json={}).json()["detail"]["code"] == "nothing_to_save"


def test_tc10_photo_rules():
    with_app()
    r = upload()
    assert r.status_code == 200 and r.json()["file_id"] == DB.files[0]["id"]
    assert DB.files[0]["kind"] == "id_document" and len(r.json()["id_documents"]) == 1 and DB.objects
    assert code(api.post(f"{P}/files", json={"kind": "id_document", "file_base64": photo(6)})) == "file_too_large"
    assert code(api.post(f"{P}/files", json={"kind": "id_document",
                                            "file_base64": base64.b64encode(b"MZ\x90\x00").decode()})) == "invalid_file_type"
    assert upload().status_code == 200
    r = upload()
    assert r.status_code == 400 and code(r) == "too_many_files"
    DB.apps[f"app-{SID}"]["id_type"] = "cccd"
    assert code(upload()) == "id_document_not_needed"
    assert len(DB.files) == 2


def test_tc10_photo_needs_an_application():
    r = upload()
    assert r.status_code == 409 and code(r) == "identity_required"


def test_tc20_tax_only_without_application():
    r = api.put(P, json={"tax": {"tax_resident": False}})
    assert r.status_code == 400 and r.json()["detail"]["groups"] == ["identity"]
    assert DB.apps == {} and DB.sellers[SID]["tax_resident"] is True


def test_tc23_no_personal_data_in_logs(monkeypatch, caplog):
    with_app()

    def boom(*a):
        raise RuntimeError('duplicate key: (id_number)=(P7654321) Maria Santos Reyes 0123456789 0312345678')
    monkeypatch.setattr(FakeDAO, "update_application", boom)
    with caplog.at_level(logging.DEBUG):
        assert api.put(P, json=identity(id_number="P7654321")).status_code == 500
        assert api.put(P, json={"tax": {"tax_resident": True, "tax_code": "0312345678"}}).status_code == 500
        assert api.put(P, json=identity(id_type="cccd", id_number="12345")).status_code == 400
    for secret in ("P7654321", "Maria", "0123456789", "0312345678", "12345"):
        assert secret not in caplog.text, secret


def test_tc24_empty_or_masked_number_keeps_the_stored_one():
    with_app()
    for value in ("", "•••• 4567"):
        r = api.put(P, json=identity(id_number=value))
        assert r.status_code == 200 and "id_number" not in r.json()["changed"]
        assert DB.apps[f"app-{SID}"]["id_number"] == "P1234567"


def test_tc25_same_body_twice():
    with_app()
    body = identity(residential_address="9 Nguyen Hue")
    assert api.put(P, json=body).json()["changed"] == ["residential_address"]
    assert api.put(P, json=body).json()["changed"] == []


def test_tc26_bank_saved_and_snapshotted():
    with_app()
    DB.sellers[SID].update(bank_name=None, bank_account_number=None, bank_account_holder=None)
    r = api.put(P, json=bank(bank_account_holder="MARIA SANTOS REYES", bank_account_number="0123456789"))
    assert r.status_code == 200 and "bank_account_number" in r.json()["changed"]
    assert DB.sellers[SID]["bank_account_number"] == "0123456789" == r.json()["bank"]["bank_account_number"]
    assert DB.apps[f"app-{SID}"]["bank_account_holder"] == "MARIA SANTOS REYES"


@pytest.mark.parametrize("change,err", [
    ({"bank_account_holder": "MARIA REYES"}, "bank_holder_mismatch"),
    ({"bank_account_number": "12345"}, "invalid_bank_account"),
    ({"bank_name": ""}, "missing_field"),
])
def test_tc27_bank_refused(change, err):
    with_app()
    r = api.put(P, json=bank(**change))
    assert r.status_code == 400 and code(r) == err and DB.writes == []


@pytest.mark.parametrize("body", [bank(), bank(bank_account_holder="NGUOI KHAC"), {**bank(), "tax": {"tax_resident": True}}])
def test_tc28_tc38_bank_without_application(body):
    r = api.put(P, json=body)
    assert r.status_code == 409 and code(r) == "identity_required"
    assert DB.writes == [] and DB.apps == {}


def test_join_row_keeps_its_values_when_seller_lacks_them():
    """A /join row (its CHECK keeps bank / phone filled) is never overwritten with null from seller_profiles."""
    with_app(source="join")
    DB.sellers[SID]["phone"] = None
    assert api.put(P, json=identity(residential_address="9 Nguyen Hue")).status_code == 200
    assert DB.apps[f"app-{SID}"]["phone"] == "+84901234567"


def two_photos():
    with_app()
    upload(), upload()
    return [f["id"] for f in DB.files]


def test_tc30_delete_one_photo():
    first, second = two_photos()
    path = DB.files[0]["storage_path"]
    r = api.delete(f"{P}/files/{first}")
    assert r.status_code == 200 and [p["id"] for p in r.json()["id_documents"]] == [second]
    assert path not in DB.objects and len(DB.objects) == 1


def test_tc31_delete_only_this_sellers_passport_photo():
    first, _ = two_photos()
    DB.apps["app-other"] = application(OTHER, id="app-other")
    DB.files.append({"id": "44444444-4444-4444-8444-444444444441", "application_id": f"app-{SID}",
                     "kind": "dish_photo", "storage_path": "d.jpg", "content_type": "image/jpeg"})
    other = f"/rest/v1/admin-gateway/sellers/{OTHER}/kyc/files/{first}"
    for path in (other, f"{P}/files/55555555-5555-4555-8555-555555555555",
                 f"{P}/files/44444444-4444-4444-8444-444444444441"):
        assert api.delete(path).status_code == 404, path
    assert len(DB.files) == 3 and len(DB.objects) == 2


def test_tc32_object_already_gone():
    first, _ = two_photos()
    DB.objects.discard(DB.files[0]["storage_path"])
    assert api.delete(f"{P}/files/{first}").status_code == 200 and len(DB.files) == 1


def test_tc37_delete_both_then_add_again():
    first, second = two_photos()
    api.delete(f"{P}/files/{first}"), api.delete(f"{P}/files/{second}")
    assert "id_document" in seller_missing()
    assert upload().status_code == 200 and len(DB.files) == 1


def test_tc11_seller_form_reports_the_name_before_the_bank():
    """QĐ-1: the seller route's error order is kept: a bad name fix comes before a bad account number."""
    from fastapi import HTTPException
    from schemas import Schema
    body = Schema.RequestSellerProfileCompletion(full_name="1234", bank={"bank_name": "VCB", "bank_account_number": "12",
                                                                           "bank_account_holder": "X"})
    with pytest.raises(HTTPException) as e:
        spc.check_kyc(body, None, seller(SID), spc._settings())
    assert e.value.detail["code"] == "invalid_full_name"
