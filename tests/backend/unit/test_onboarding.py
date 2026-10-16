"""Public seller application (/join): create -> upload files -> submit.
DAO, storage and Turnstile are faked. No DB, no network.

Run from tests/backend:  pytest unit/test_onboarding.py
"""
import base64
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
FEES = {"community": 0, "tindahan": 720000, "negosyo": 1200000, "enterprise": 2200000, "founding": 720000}


class FakeConfig:
    raw = {}   # admin_settings rows as stored (any JSON value); missing = no row

    def get_positive_ints(self, defaults):
        # Real validation: only the DB read is faked.
        return {k: DAOAdminConfig._positive_int(k, self.raw.get(k), d) for k, d in defaults.items()}


class FakeDAO:
    apps = {}
    files = {}

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


class FakeResponse:
    def __init__(self, success):
        self._success = success

    def json(self):
        return {"success": self._success}


@pytest.fixture
def env(monkeypatch):
    FakeDAO.apps, FakeDAO.files = {}, {}
    FakeConfig.raw = {}
    monkeypatch.setattr(onboarding, "DAOAdminConfig", FakeConfig)
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
        "first_name": "Maria", "last_name": "Santos", "date_of_birth": adult.isoformat(),
        "nationality": "Philippines", "id_type": "passport", "id_number": "P1234567",
        "email": "maria@example.com", "phone": "0901234567",
        "residential_address": "12 Nguyen Hue, District 1",
        "store_name": "Maria's Kitchen", "pickup_address": "12 Nguyen Hue, District 1",
        "maps_link": "https://maps.app.goo.gl/abc123",
        "opening_time": "09:00", "closing_time": "20:00",
        "menu": [_dish("a"), _dish("b")],
        "tier": "tindahan",
        "bank_name": "Vietcombank", "bank_account_number": "0123456789", "bank_account_holder": "MARIA SANTOS",
        "agreed": True, "agreement_version": onboarding.SETTINGS_DEFAULTS["seller_agreement_version"],
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
    assert res["max_dish_price"] == 10_000_000 and res["min_age"] == 18 and res["agreement_version"] == 20261016
    assert [t["tier"] for t in res["tiers"]] == ["community", "tindahan", "negosyo", "enterprise"]
    assert res["tiers"][0]["max_items"] == 3 and res["tiers"][3]["max_items"] is None
    assert res["tiers"][1]["monthly_fee_vnd"] == 720000
    assert res["tiers"][1]["commission_percent"] == 17
    assert res["founding"] == {"slots": 50, "free_months": 4, "commission_percent": 17, "monthly_fee_vnd": 720000}


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
