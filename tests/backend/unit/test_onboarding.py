"""Public seller application (/join): create -> upload files -> submit.
DAO, storage and Turnstile are faked. No DB, no network.

Run from tests/backend:  pytest unit/test_onboarding.py
"""
import base64
import logging
import io
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from apis import onboarding
from dao.dao_admin_config import DAOAdminConfig

TIER_LIMITS = {
    "community": {"max_items": 3, "max_categories": 1},
    "tindahan": {"max_items": 30, "max_categories": 5},
    "negosyo": {"max_items": 90, "max_categories": 10},
    "enterprise": {"max_items": None, "max_categories": None},
    "founding": {"max_items": None, "max_categories": None},
}
FEES = {"community": 0, "tindahan": 750000, "negosyo": 1250000, "enterprise": 2300000, "founding": 750000}


class FakeConfig:
    raw = {}   # admin_settings rows as stored (any JSON value); missing = no row

    def get_positive_ints(self, defaults):
        # Real validation: only the DB read is faked.
        return {k: DAOAdminConfig._positive_int(k, self.raw.get(k), d) for k, d in defaults.items()}


class FakeDAO:
    apps = {}
    files = {}
    taken = set()   # emails of existing Sariko accounts, lower case

    def email_has_account(self, email):
        return email.strip().lower() in self.taken

    def get_tier_limits(self, tier):
        return TIER_LIMITS.get(tier)

    def list_tiers(self, tiers):
        return [{"tier": t, "commission_rate": 0.17, "monthly_fee_vnd": FEES[t], **TIER_LIMITS[t]} for t in tiers]

    def create_application(self, data):
        app_id = f"abcdef12-0000-0000-0000-{len(self.apps):012d}"
        row = {**data, "id": app_id, "created_at": datetime.now(timezone.utc).isoformat()}
        self.apps[app_id] = row
        return row

    def get_application(self, application_id):
        return self.apps.get(application_id)

    def list_files(self, application_id):
        return [f for f in self.files.values() if f["application_id"] == application_id]

    def create_file(self, data):
        file_id = f"file-{len(self.files) + 1}"
        while file_id in self.files:
            file_id += "x"
        self.files[file_id] = {**data, "id": file_id}
        return self.files[file_id]

    def delete_file(self, file_id):
        self.files.pop(file_id, None)

    def submit(self, application_id):
        app = self.apps.get(application_id)
        if not app or app["status"] != "draft":
            return False
        app.update(status="submitted", upload_token=None)
        return True


class FakeProfiles:
    enterprise = 0   # sellers already on the enterprise plan

    def count_sellers_by_tier(self, tier):
        assert tier == "enterprise"
        return self.enterprise


class FakeResponse:
    def __init__(self, success):
        self._success = success

    def json(self):
        return {"success": self._success}


@pytest.fixture
def env(monkeypatch):
    FakeDAO.apps, FakeDAO.files, FakeDAO.taken = {}, {}, set()
    FakeConfig.raw = {}
    FakeProfiles.enterprise = 0
    monkeypatch.setattr(onboarding, "DAOAdminConfig", FakeConfig)
    monkeypatch.setattr(onboarding, "DAOSellerProfiles", FakeProfiles)
    onboarding._rate_hits.clear()
    storage = {"uploaded": [], "removed": []}
    captcha = {"success": True}
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(onboarding, "DAOOnboarding", FakeDAO)
    monkeypatch.setattr(onboarding.requests, "post", lambda *a, **kw: FakeResponse(captcha["success"]))
    monkeypatch.setattr(onboarding, "upload_private", lambda bucket, path, content, ct: storage["uploaded"].append((path, content, ct)))
    monkeypatch.setattr(onboarding, "remove_private", lambda bucket, path: storage["removed"].append(path))
    app = FastAPI()
    app.include_router(onboarding.router)
    return {"client": TestClient(app), "storage": storage, "captcha": captcha}


def _dish(key, category="Ulam", name=None, price=75000):
    return {"key": key, "category": category, "name": name or f"Dish {key}", "price": price, "preorder_day": 0}


def _body(**over):
    adult = date.today().replace(year=date.today().year - 30)
    body = {
        "full_name": "Maria Santos", "date_of_birth": adult.isoformat(),
        "nationality": "Philippines", "id_type": "passport", "id_number": "P1234567",
        "id_expiry_date": "2035-01-01", "tax_resident": True,
        "email": "maria@example.com", "phone": "0901234567",
        "residential_address": "12 Nguyen Hue, District 1",
        "store_name": "Maria's Kitchen", "pickup_address": "12 Nguyen Hue, District 1",
        "maps_link": "https://maps.app.goo.gl/abc123",
        "opening_time": "09:00", "closing_time": "20:00",
        "menu": [_dish("a"), _dish("b")],
        "tier": "tindahan",
        "bank_name": "Vietcombank", "bank_account_number": "0123456789", "bank_account_holder": "MARIA SANTOS",
        "agreed": True, "personal_data_consent": True,
        "agreement_version": onboarding.SETTINGS_DEFAULTS["seller_agreement_version"],
        "signature_name": "maria  santos", "turnstile_token": "tok",
    }
    body.update(over)
    return body


def _jpeg(size=(50, 50)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


PDF = base64.b64encode(b"%PDF-1.4 test").decode()


def _create(env, **over):
    res = env["client"].post("/onboarding/applications", json=_body(**over))
    assert res.status_code == 200, res.json()
    return res.json()["id"], res.json()["upload_token"]


def _upload(env, app_id, token, kind, data, item_key=None):
    return env["client"].post(
        f"/onboarding/applications/{app_id}/files",
        json={"kind": kind, "item_key": item_key, "file_base64": data},
        headers={"X-Upload-Token": token},
    )


def _code(res):
    return res.json()["detail"]["code"]


# ── create ─────────────────────────────────────────────────────────────────

def test_create_ok_stores_normalised_draft(env):
    app_id, token = _create(env, menu=[_dish("a", category="  ulam  dishes ")])
    row = FakeDAO.apps[app_id]
    assert row["status"] == "draft" and row["upload_token"] == token
    assert row["phone"] == "+84901234567"
    assert row["menu"][0]["category"] == "Ulam dishes"
    assert row["menu"][0]["price"] == 75000


def test_captcha_failed(env):
    env["captcha"]["success"] = False
    res = env["client"].post("/onboarding/applications", json=_body())
    assert res.status_code == 400 and _code(res) == "captcha_failed"


def test_missing_turnstile_secret_fails_closed(env, monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET_KEY")
    assert env["client"].post("/onboarding/applications", json=_body()).status_code == 500


def test_under_18(env):
    dob = date.today() - timedelta(days=17 * 365)
    res = env["client"].post("/onboarding/applications", json=_body(date_of_birth=dob.isoformat()))
    assert _code(res) == "under_age"


def test_signature_must_match_name_either_order(env):
    assert _code(env["client"].post("/onboarding/applications", json=_body(signature_name="Maria Cruz"))) == "signature_mismatch"
    _create(env, signature_name="SANTOS Maria")


def test_outdated_agreement(env):
    res = env["client"].post("/onboarding/applications", json=_body(agreement_version=20200101))
    assert res.status_code == 409 and _code(res) == "agreement_outdated"


def test_plan_limits(env):
    four = [_dish(k) for k in "abcd"]
    res = env["client"].post("/onboarding/applications", json=_body(tier="community", menu=four))
    assert _code(res) == "too_many_items" and res.json()["detail"]["limit"] == 3
    two_cats = [_dish("a", "Ulam"), _dish("b", "Dessert")]
    assert _code(env["client"].post("/onboarding/applications", json=_body(tier="community", menu=two_cats))) == "too_many_categories"


@pytest.mark.parametrize("price", [0, -1, 10_000_001])
def test_invalid_price(env, price):
    res = env["client"].post("/onboarding/applications", json=_body(menu=[_dish("a", price=price)]))
    assert _code(res) == "invalid_price"


@pytest.mark.parametrize("price", [75000.5, 75000.0, "75000", True])
def test_price_must_be_a_json_integer(env, price):
    # Money is whole VND: no float, no string coercion (StrictInt) -> 422 before any check.
    res = env["client"].post("/onboarding/applications", json=_body(menu=[_dish("a", price=price)]))
    assert res.status_code == 422


def test_duplicate_dish_name_in_category(env):
    menu = [_dish("a", name="Leche Flan"), _dish("b", category="ulam", name="leche  flan")]
    assert _code(env["client"].post("/onboarding/applications", json=_body(menu=menu))) == "duplicate_dish"
    _create(env, menu=[_dish("a", name="Leche Flan"), _dish("b", category="Dessert", name="Leche Flan")])


def test_invalid_maps_link(env):
    res = env["client"].post("/onboarding/applications", json=_body(maps_link="https://evil.example/maps"))
    assert _code(res) == "invalid_maps_link"
    _create(env, maps_link="https://www.google.com/maps/place/@10.77,106.70,17z")


def test_rate_limit_sixth_is_429(env):
    for _ in range(onboarding.SETTINGS_DEFAULTS["onboarding_rate_limit_per_hour"]):
        _create(env)
    res = env["client"].post("/onboarding/applications", json=_body())
    assert res.status_code == 429


# ── settings (admin_settings, read on every request) ─────────────────────

def test_settings_endpoint_serves_defaults_and_plan_limits(env):
    res = env["client"].get("/onboarding/settings").json()
    assert res["max_dish_price"] == 10_000_000 and res["min_age"] == 18 and res["agreement_version"] == 20261023
    assert [t["tier"] for t in res["tiers"]] == ["community", "tindahan", "negosyo", "enterprise"]
    assert res["tiers"][0]["max_items"] == 3 and res["tiers"][3]["max_items"] is None
    assert res["tiers"][1]["monthly_fee_vnd"] == 750000
    assert res["tiers"][1]["commission_percent"] == 17
    assert res["founding"] == {"slots": 50, "free_months": 4, "commission_percent": 17, "monthly_fee_vnd": 750000}
    assert res["enterprise"] == {"slots": 5, "taken": 0}


def test_tc4_enterprise_places(env):
    FakeProfiles.enterprise = 2
    assert env["client"].get("/onboarding/settings").json()["enterprise"] == {"slots": 5, "taken": 2}
    _create(env, tier="enterprise")                       # 3 places left

    FakeProfiles.enterprise = 5
    res = env["client"].post("/onboarding/applications", json=_body(tier="enterprise"))
    assert res.status_code == 409 and _code(res) == "enterprise_full"
    _create(env, tier="tindahan")                         # other plans are not capped

    FakeConfig.raw = {"enterprise_slots": 6}              # admin adds a place
    _create(env, tier="enterprise")


def test_percent_uses_decimal_half_up():
    assert onboarding._percent(0.17) == 17      # float 0.17 * 100 = 17.000000000000004
    assert onboarding._percent(0.145) == 15     # half up, not banker's / float drift
    assert onboarding._percent("0.13") == 13


def test_changed_setting_applies_at_once(env):
    FakeConfig.raw = {"onboarding_max_dish_price": 50000, "onboarding_min_age": 40}
    res = env["client"].post("/onboarding/applications", json=_body())
    assert _code(res) == "under_age" and res.json()["detail"]["min_age"] == 40
    FakeConfig.raw = {"onboarding_max_dish_price": 50000}
    res = env["client"].post("/onboarding/applications", json=_body())
    assert _code(res) == "invalid_price" and res.json()["detail"]["max"] == 50000
    assert env["client"].get("/onboarding/settings").json()["max_dish_price"] == 50000


def test_tc11_agreement_20261021(env):
    FakeConfig.raw = {"seller_agreement_version": 20261021}            # after migration 20261021040000
    assert env["client"].get("/onboarding/settings").json()["agreement_version"] == 20261021
    res = env["client"].post("/onboarding/applications", json=_body(agreement_version=20261018))   # page opened before
    assert res.status_code == 409 and _code(res) == "agreement_outdated"
    _create(env, agreement_version=20261021)
    FakeConfig.raw = {}                                                 # row missing: the default is the new text too
    _create(env, agreement_version=20261023)


def test_new_agreement_version_rejects_old_signature(env):
    FakeConfig.raw = {"seller_agreement_version": 20270101}
    assert _code(env["client"].post("/onboarding/applications", json=_body())) == "agreement_outdated"
    _create(env, agreement_version=20270101)


@pytest.mark.parametrize("bad", [0, -5, "abc", True, 1.5, None])
def test_invalid_setting_falls_back_to_default(env, bad):
    FakeConfig.raw = {"onboarding_max_dish_price": bad, "onboarding_min_age": bad}
    _create(env)   # 75.000 ₫ and a 30-year-old pass the defaults (10.000.000, 18)
    assert env["client"].get("/onboarding/settings").json()["max_dish_price"] == 10_000_000


def test_upload_window_setting(env):
    app_id, token = _create(env)
    FakeDAO.apps[app_id]["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    FakeConfig.raw = {"onboarding_upload_window_minutes": 10}
    assert _upload(env, app_id, token, "id_document", _jpeg()).status_code == 404


# ── files ──────────────────────────────────────────────────────────────────

def test_wrong_token_expired_or_not_draft_is_404(env):
    app_id, token = _create(env)
    assert _upload(env, app_id, "wrong", "id_document", _jpeg()).status_code == 404
    assert _upload(env, "no-such-id", token, "id_document", _jpeg()).status_code == 404
    FakeDAO.apps[app_id]["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    assert _upload(env, app_id, token, "id_document", _jpeg()).status_code == 404


def test_magic_bytes_and_size(env):
    app_id, token = _create(env)
    fake = base64.b64encode(b"GIF89a....").decode()
    assert _code(_upload(env, app_id, token, "id_document", fake)) == "invalid_file_type"
    big = base64.b64encode(b"%PDF" + b"0" * 5 * 1024 * 1024).decode()
    assert _code(_upload(env, app_id, token, "food_safety", big)) == "file_too_large"
    assert _code(_upload(env, app_id, token, "dish_photo", PDF, item_key="a")) == "invalid_file_type"


def test_image_is_compressed_to_jpeg_pdf_kept(env):
    app_id, token = _create(env)
    assert _upload(env, app_id, token, "id_document", _jpeg((3000, 2000))).status_code == 200
    assert _upload(env, app_id, token, "food_safety", PDF).status_code == 200
    (img_path, img, img_ct), (pdf_path, pdf, pdf_ct) = env["storage"]["uploaded"]
    assert img_path.startswith(f"{app_id}/id_document-") and img_path.endswith(".jpg") and img_ct == "image/jpeg"
    assert max(Image.open(io.BytesIO(img)).size) == 1600
    assert pdf_path.endswith(".pdf") and pdf_ct == "application/pdf" and pdf.startswith(b"%PDF")


def test_max_two_files_per_document_kind(env):
    app_id, token = _create(env)
    for _ in range(2):
        assert _upload(env, app_id, token, "id_document", _jpeg()).status_code == 200
    assert _code(_upload(env, app_id, token, "id_document", _jpeg())) == "too_many_files"


def test_dish_photo_unknown_key_and_replace(env):
    app_id, token = _create(env)
    assert _code(_upload(env, app_id, token, "dish_photo", _jpeg(), item_key="zzz")) == "unknown_dish"
    first = _upload(env, app_id, token, "dish_photo", _jpeg(), item_key="a").json()["file_id"]
    second = _upload(env, app_id, token, "dish_photo", _jpeg(), item_key="a").json()["file_id"]
    photos = [f for f in FakeDAO.files.values() if f["kind"] == "dish_photo"]
    assert [f["id"] for f in photos] == [second] and first != second
    assert env["storage"]["removed"] == [env["storage"]["uploaded"][0][0]]


# ── submit ─────────────────────────────────────────────────────────────────

def _submit(env, app_id, token):
    return env["client"].post(f"/onboarding/applications/{app_id}/submit", headers={"X-Upload-Token": token})


def test_submit_requires_id_document_and_every_dish_photo(env):
    app_id, token = _create(env)
    assert _code(_submit(env, app_id, token)) == "id_document_required"
    _upload(env, app_id, token, "id_document", _jpeg())
    _upload(env, app_id, token, "dish_photo", _jpeg(), item_key="a")
    res = _submit(env, app_id, token)
    assert _code(res) == "dish_photo_missing" and res.json()["detail"]["keys"] == ["b"]


def test_submit_ok_then_second_submit_is_404(env):
    app_id, token = _create(env)
    _upload(env, app_id, token, "id_document", _jpeg())
    for key in ("a", "b"):
        _upload(env, app_id, token, "dish_photo", _jpeg(), item_key=key)
    res = _submit(env, app_id, token)
    assert res.status_code == 200 and res.json()["reference"] == app_id[:8].upper()
    assert FakeDAO.apps[app_id]["status"] == "submitted" and FakeDAO.apps[app_id]["upload_token"] is None
    assert _submit(env, app_id, token).status_code == 404


# ── Q6 / Q9-Q12 (spec docs/dev/seller-profile-completion, TC-33..35) ──────────

CCCD = {"nationality": "Vietnam", "id_type": "cccd", "id_number": "079090001234",
        "full_name": "Nguyễn Văn An", "signature_name": "Nguyễn Văn An",
        "bank_account_holder": "NGUYEN VAN AN"}


def test_tc33_cccd_seller_needs_no_photo(env):
    app_id, token = _create(env, **CCCD)
    assert _code(_upload(env, app_id, token, "id_document", _jpeg())) == "id_document_not_needed"
    for key in ("a", "b"):
        _upload(env, app_id, token, "dish_photo", _jpeg(), item_key=key)
    assert _submit(env, app_id, token).status_code == 200


def test_tc34_passport_seller_still_needs_the_photo(env):
    app_id, token = _create(env)
    for key in ("a", "b"):
        _upload(env, app_id, token, "dish_photo", _jpeg(), item_key=key)
    assert _code(_submit(env, app_id, token)) == "id_document_required"


@pytest.mark.parametrize("over,code", [
    ({"id_expiry_date": None}, "id_expiry_required"),
    ({"id_expiry_date": (date.today() - timedelta(days=1)).isoformat()}, "id_expired"),
    ({"id_expiry_date": (date.today() + timedelta(days=60)).isoformat()}, "id_expiring"),
    ({**CCCD, "id_number": "12345"}, "invalid_id_number"),
    ({"tax_resident": None}, "missing_field"),
    ({"personal_data_consent": False}, "consent_required"),
    ({"bank_account_number": "12345"}, "invalid_bank_account"),
    ({"bank_account_holder": "JUAN CRUZ"}, "bank_holder_mismatch"),
])
def test_tc35_identity_rules(env, over, code):
    res = env["client"].post("/onboarding/applications", json=_body(**over))
    assert res.status_code == 400 and _code(res) == code
    assert FakeDAO.apps == {}


def test_tc35_stores_expiry_and_consent(env):
    app_id, _ = _create(env, **CCCD)
    row = FakeDAO.apps[app_id]
    assert row["id_expiry_date"] == "2035-01-01" and row["personal_data_consent_at"]


def test_tc35_months_setting_is_served_and_applied(env):
    FakeConfig.raw = {"onboarding_min_id_validity_months": 1}
    assert env["client"].get("/onboarding/settings").json()["min_id_validity_months"] == 1
    _create(env, id_expiry_date=(date.today() + timedelta(days=60)).isoformat())


# ── One full name box (docs/dev/seller-full-name N1-N6, TC ids in the names) ────

def _refused_name(env, status, code, **over):
    res = env["client"].post("/onboarding/applications", json=_body(**over))
    assert res.status_code == status and res.json()["detail"]["code"] == code, res.text
    assert FakeDAO.apps == {}
    return res


def test_tc3_full_name_is_stored_squashed_without_first_last(env):
    app_id, _ = _create(env, full_name="  Nguyễn   Văn\tÂn ", signature_name="Nguyễn Văn Ân",
                        bank_account_holder="NGUYEN VAN AN")
    row = FakeDAO.apps[app_id]
    assert row["full_name"] == "Nguyễn Văn Ân" and "first_name" not in row and "last_name" not in row


def test_tc3_no_name_at_all_is_a_readable_422(env):
    res = _refused_name(env, 422, "missing_field", full_name="  ")
    assert res.json()["detail"]["field"] == "full_name"


def test_tc1_tc4_holder_and_signature_by_words(env):
    _refused_name(env, 400, "bank_holder_mismatch", **{**CCCD, "bank_account_holder": "NGUYEN AN"})   # no middle name
    _refused_name(env, 400, "signature_mismatch", **{**CCCD, "signature_name": "Nguyen Van An"})      # accents dropped
    _create(env, **{**CCCD, "bank_account_holder": "AN VAN NGUYEN", "signature_name": "Ân Văn Nguyễn",
                    "full_name": "Nguyễn Văn Ân"})


def test_tc12_old_client_first_last_is_joined(env):
    over = {k: v for k, v in _body().items() if k != "full_name"}
    res = env["client"].post("/onboarding/applications", json={**over, "first_name": " Ân ", "last_name": "Nguyễn  Văn",
                                                                 "bank_account_holder": "NGUYEN VAN AN",
                                                                 "signature_name": "Nguyễn Văn Ân"})
    assert res.status_code == 200, res.text
    assert FakeDAO.apps[res.json()["id"]]["full_name"] == "Ân Nguyễn Văn"


def test_tc12_full_name_wins_over_first_last(env):
    app_id, _ = _create(env, full_name="Maria Cruz Santos", first_name="X", last_name="Y",
                        signature_name="Maria Cruz Santos", bank_account_holder="MARIA CRUZ SANTOS")
    assert FakeDAO.apps[app_id]["full_name"] == "Maria Cruz Santos"


@pytest.mark.parametrize("name", ["An2", "<script>", "=1+1", "An@", "Nguyễn, An", "..."])
def test_tc15_other_characters_refused(env, name):
    res = _refused_name(env, 422, "invalid_full_name", full_name=name)
    assert res.json()["detail"]["field"] == "full_name"


@pytest.mark.parametrize("name", ["An", "Anne-Marie O'Brien Jr."])
def test_tc15_one_word_and_punctuation_pass(env, name):
    app_id, _ = _create(env, full_name=name, signature_name=name, bank_account_holder=name.upper())
    assert FakeDAO.apps[app_id]["full_name"] == name


def test_tc15_301_characters_refused(env):
    res = env["client"].post("/onboarding/applications", json=_body(full_name="A" * 301))
    assert res.status_code == 422 and FakeDAO.apps == {}
    assert [e["loc"][-1] for e in res.json()["detail"]] == ["full_name"]


def test_tc22_name_not_in_logs_or_422(env, caplog, monkeypatch, tmp_path):
    caplog.set_level(logging.DEBUG)
    monkeypatch.chdir(tmp_path)   # main makes ./logs on import; tests are read-only in CI
    import main
    env["client"].app.add_exception_handler(main.RequestValidationError, main.validation_exception_handler)
    env["client"].app.add_exception_handler(main.HTTPException, main.http_exception_handler)
    secret = "Zyxwvu Qponml"
    for over in ({"full_name": secret + "x" * 300}, {"full_name": secret + "1"},
                 {"full_name": secret, "bank_account_holder": "OTHER PERSON"}, {"full_name": secret, "signature_name": "x"}):
        res = env["client"].post("/onboarding/applications", json=_body(**over))
        assert res.status_code in (400, 422) and "Zyxwvu" not in res.text
    assert "Zyxwvu" not in caplog.text


def test_tc21_two_posts_two_drafts_each_with_its_own_name(env):
    a, _ = _create(env)
    b, _ = _create(env, full_name="Maria Cruz Santos", signature_name="Maria Cruz Santos", bank_account_holder="MARIA CRUZ SANTOS")
    assert (FakeDAO.apps[a]["full_name"], FakeDAO.apps[b]["full_name"]) == ("Maria Santos", "Maria Cruz Santos")


# ── join-review T2: an email that already has a Sariko account ──────────────

def test_t2_email_with_an_account_is_refused_at_create(env):
    FakeDAO.taken = {"maria@example.com"}
    res = env["client"].post("/onboarding/applications", json=_body(email="  Maria@Example.COM "))
    assert res.status_code == 409 and res.json()["detail"]["code"] == "email_has_account"
    assert res.json()["detail"]["field"] == "email" and FakeDAO.apps == {}
    assert sum(len(hits) for hits in onboarding._rate_hits.values()) == 1   # the refused try counts toward the limit


def test_t2_lookup_is_an_exact_lower_case_match():
    """No pattern: a '*' or '_' in an address matches only itself (users.email is lower case, from Supabase Auth)."""
    from dao.dao_onboarding import DAOOnboarding
    calls = []

    class Query:
        def __getattr__(self, name):
            return lambda *a: calls.append((name, a)) or self

        def execute(self):
            return type("R", (), {"data": []})()
    dao = DAOOnboarding.__new__(DAOOnboarding)
    dao._supabase_client = type("C", (), {"table": lambda self, t: calls.append(("table", (t,))) or Query()})()
    assert dao.email_has_account("  A*B_c@Example.com ") is False
    assert ("eq", ("email", "a*b_c@example.com")) in calls and not any(n in ("ilike", "like") for n, _ in calls)


def _ready(env, **over):
    app_id, token = _create(env, **over)
    _upload(env, app_id, token, "id_document", _jpeg())
    _upload(env, app_id, token, "food_safety", PDF)
    for key in ("a", "b"):
        _upload(env, app_id, token, "dish_photo", _jpeg(), item_key=key)
    return app_id, token


def test_t2_account_made_after_create_is_refused_at_submit(env, mail):
    app_id, token = _ready(env)
    FakeDAO.taken = {"maria@example.com"}
    assert _code(_submit(env, app_id, token)) == "email_has_account"
    assert FakeDAO.apps[app_id]["status"] == "draft" and mail["sent"] == [] and mail["zalo"] == []


# ── join-review E1 / E2: emails and the ops message on submit ───────────────

class Inline:
    """threading.Thread that runs at once, so the background email is checked in the test."""
    def __init__(self, target, args=(), daemon=None):
        self.run = lambda: target(*args)

    def start(self):
        self.run()


@pytest.fixture
def mail(monkeypatch):
    out = {"sent": [], "zalo": [], "fail": False}

    def send(to, subject, body, reply_to=None):
        if out["fail"]:
            raise OSError("smtp down")
        out["sent"].append({"to": to, "subject": subject, "body": body, "reply_to": reply_to})
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setenv("ENV", "prd")
    monkeypatch.setattr(onboarding.email_service, "send", send)
    monkeypatch.setattr(onboarding.zalo, "send", lambda kind, text: out["zalo"].append((kind, text)))
    monkeypatch.setattr(onboarding, "threading", type("T", (), {"Thread": Inline}))
    return out


def test_e1_e2_on_submit_prod(env, mail):
    app_id, token = _ready(env)
    assert _submit(env, app_id, token).status_code == 200
    seller, ops = mail["sent"]
    code = app_id[:8].upper()
    assert seller["to"] == "maria@example.com" and seller["subject"] == "We received your Sariko seller application"
    assert seller["reply_to"] == "support@sariko.store"
    for text in (f"Application code: {code}", "Full name: Maria Santos", "Store: Maria's Kitchen",
                 "Pickup address: 12 Nguyen Hue, District 1", "Plan: Tindahan", "Menu: 2 dishes in 1 category",
                 "Payout account: Vietcombank, account ending 6789", "(Vietnam time)",
                 "Documents received: Passport photo page (1), Food safety certificate (1), Dish photos (2)"):
        assert text in seller["body"], text
    assert ops["to"] == "support@sariko.store" and code in ops["subject"] and ops["reply_to"] == "maria@example.com"
    assert f"/seller-applications?open={app_id}" in ops["body"]
    [(kind, text)] = mail["zalo"]
    assert kind == "ops" and code in text and "Maria's Kitchen" in text
    for m in mail["sent"]:   # never the ID number or the whole account number
        assert "P1234567" not in m["body"] and "0123456789" not in m["body"]


def test_t1_not_prod_sends_the_seller_email_to_support_tagged(env, mail, monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    app_id, token = _ready(env)
    _submit(env, app_id, token)
    seller, ops = mail["sent"]
    assert seller["to"] == "support@sariko.store" and seller["subject"] == "[TEST DEV] We received your Sariko seller application"
    assert ops["subject"].startswith("[TEST DEV] New seller application")


def test_submit_succeeds_when_smtp_or_zalo_fail(env, mail, monkeypatch):
    mail["fail"] = True
    app_id, token = _ready(env)
    assert _submit(env, app_id, token).status_code == 200 and FakeDAO.apps[app_id]["status"] == "submitted"

    def down(kind, text):
        raise RuntimeError("zalo down")
    monkeypatch.setattr(onboarding.zalo, "send", down)
    app_id, token = _ready(env, email="other@example.com")
    assert _submit(env, app_id, token).status_code == 200 and FakeDAO.apps[app_id]["status"] == "submitted"


def test_no_email_when_smtp_not_configured(env, mail, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD")
    app_id, token = _ready(env)
    assert _submit(env, app_id, token).status_code == 200
    assert mail["sent"] == [] and len(mail["zalo"]) == 1
