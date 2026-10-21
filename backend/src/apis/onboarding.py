"""Public seller application form (/join). No login: the seller has no account yet.

Three steps because nginx caps a request body at 10 MB: create (all text + menu,
behind Turnstile) -> upload each file with the one-off upload token -> submit.
The checks in create are the ones Jack used to do by hand on the Excel menu.
"""
import base64
import binascii
import hmac
import logging
import os
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Header, HTTPException, Request

from core.client_ip import client_ip
from core.phone import to_e164_vn
from core.seller_kyc import age, bank_holder_matches, id_error, same_name, valid_bank_account
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_onboarding import DAOOnboarding
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema
from utils.storage import compress_to_jpeg, remove_private, upload_private

router = APIRouter(prefix="/onboarding")
logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
BUCKET = "onboarding-files"
TIERS = ("community", "tindahan", "negosyo", "enterprise")
FILE_KINDS = ("id_document", "residence_card", "food_safety", "business_registration", "dish_photo")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# admin_settings keys (editable by admin) -> default when the row is missing or invalid.
SETTINGS_DEFAULTS = {
    "onboarding_rate_limit_per_hour": 5,
    "onboarding_upload_window_minutes": 180,
    "onboarding_max_file_mb": 5,            # <= 7: nginx caps a request at 10 MB, base64 adds a third
    "onboarding_max_files_per_kind": 2,     # e.g. CCCD front + back
    "onboarding_max_dishes": 100,           # caps uploads even on an unlimited plan
    "onboarding_max_dish_price": 10_000_000,
    "onboarding_max_preorder_days": 14,
    "onboarding_min_age": 18,               # đề án III.1
    "onboarding_review_days": 2,
    "seller_agreement_version": 20261021,   # change together with public/docs/sariko_seller_agreement.html
    "onboarding_min_id_validity_months": 6, # passport valid at least this long (NĐ 248/2026 Đ18.1.b)
    "founding_slots": 50,                   # also GET /sellers/founding/slots
    "founding_free_months": 4,
    "enterprise_slots": 5,                  # Enterprise is invitation only, capped at this many sellers
}


def _settings() -> dict:
    """Read on every request so an admin change applies at once."""
    return DAOAdminConfig().get_positive_ints(SETTINGS_DEFAULTS)
MAPS_HOSTS = ("google.com", "www.google.com", "google.com.vn", "www.google.com.vn")

# ponytail: in-memory per-process limit, move to DB if we run several workers
_rate_lock = threading.Lock()
_rate_hits = defaultdict(deque)


def _error(status: int, code: str, message: str, **params):
    return HTTPException(status_code=status, detail={"code": code, "message": message, **params})


def _percent(rate) -> int:
    """0.17 -> 17, via Decimal (money rule: no float math)."""
    return int((Decimal(str(rate)) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def _vnd(amount) -> int:
    return int(Decimal(str(amount)))


def _client_ip(request: Request) -> str:
    return client_ip(request)


def _rate_limited(ip: str, limit: int) -> bool:
    cutoff = time.monotonic() - 3600
    with _rate_lock:
        hits = _rate_hits[ip]
        while hits and hits[0] < cutoff:
            hits.popleft()
        return len(hits) >= limit


def _record_hit(ip: str) -> None:
    with _rate_lock:
        _rate_hits[ip].append(time.monotonic())


def _verify_turnstile(token: str, ip: str) -> None:
    secret = os.environ.get("TURNSTILE_SECRET_KEY", "")
    if not secret:
        logger.error("TURNSTILE_SECRET_KEY not configured")
        raise HTTPException(status_code=500, detail="Server not configured")
    try:
        res = requests.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": ip},
            timeout=10,
        )
        ok = res.json().get("success") is True
    except Exception as e:
        logger.warning(f"[Onboarding] Turnstile verify failed: {repr(e)}")
        ok = False
    if not ok:
        raise _error(400, "captcha_failed", "Captcha check failed")


def _squash(text: str) -> str:
    return " ".join(text.split())


def _is_maps_link(link: str) -> bool:
    url = urlparse(link)
    host = (url.hostname or "").lower()
    if url.scheme not in ("http", "https"):
        return False
    if host == "maps.app.goo.gl":
        return True
    if host == "goo.gl":
        return url.path.startswith("/maps")
    if host in ("maps.google.com", "maps.google.com.vn"):
        return True
    return host in MAPS_HOSTS and url.path.startswith("/maps")


def _clean_menu(menu, limits: dict, settings: dict) -> list:
    """Validate the menu against the plan and normalise categories. Returns the rows to store."""
    max_price = settings["onboarding_max_dish_price"]
    max_preorder = settings["onboarding_max_preorder_days"]
    if not menu:
        raise _error(400, "menu_empty", "Add at least one dish")
    if len(menu) > settings["onboarding_max_dishes"]:
        raise _error(400, "too_many_items", "Too many dishes for this plan", limit=settings["onboarding_max_dishes"])

    rows, keys, names, categories = [], set(), set(), set()
    for item in menu:
        category = _squash(item.category)
        category = category[:1].upper() + category[1:]
        name = _squash(item.name)
        if not category or not name:
            raise _error(400, "invalid_menu", "Each dish needs a category and a name", key=item.key)
        if item.key in keys:
            raise _error(400, "invalid_menu", "Duplicate dish key", key=item.key)
        if not 0 < item.price <= max_price:
            raise _error(400, "invalid_price", "Price must be a whole number of VND", key=item.key, max=max_price)
        if not 0 <= item.preorder_day <= max_preorder:
            raise _error(400, "invalid_preorder_day", "Pre-order days out of range", key=item.key, max=max_preorder)
        # Same rule as uniq_food_items_seller_category_name, which would block the real dish later.
        name_key = (category.casefold(), name.casefold())
        if name_key in names:
            raise _error(400, "duplicate_dish", "Two dishes with the same name in one category", key=item.key, name=name)
        keys.add(item.key)
        names.add(name_key)
        categories.add(category.casefold())
        rows.append({
            "key": item.key,
            "category": category,
            "name": name,
            "description": _squash(item.description or "") or None,
            "price": item.price,
            "unit_label": _squash(item.unit_label or "") or None,
            "preorder_day": item.preorder_day,
        })

    if limits.get("max_items") is not None and len(rows) > limits["max_items"]:
        raise _error(400, "too_many_items", "Too many dishes for this plan", limit=limits["max_items"])
    if limits.get("max_categories") is not None and len(categories) > limits["max_categories"]:
        raise _error(400, "too_many_categories", "Too many categories for this plan", limit=limits["max_categories"])
    return rows


def _load_draft(dao: DAOOnboarding, application_id: str, token, settings: dict) -> dict:
    """The draft the token unlocks. Any mismatch is a 404 so the URL reveals nothing."""
    window = timedelta(minutes=settings["onboarding_upload_window_minutes"])
    app = dao.get_application(application_id)
    ok = (
        app is not None
        and app["status"] == "draft"
        and app.get("upload_token")
        and token
        and hmac.compare_digest(app["upload_token"], token)
        and datetime.now(timezone.utc) - datetime.fromisoformat(app["created_at"]) <= window
    )
    if not ok:
        raise _error(404, "application_not_found", "Application not found or expired")
    return app


def _sniff(content: bytes):
    """(content_type, ext) from magic bytes; the client's content_type is not trusted."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if content.startswith(b"\x89PNG"):
        return "image/png", "png"
    if content.startswith(b"%PDF"):
        return "application/pdf", "pdf"
    return None, None


@router.get("/settings")
def get_settings():
    """The form's limits, so the page never hardcodes them (the backend re-checks everything)."""
    s = _settings()
    rows = {r["tier"]: r for r in DAOOnboarding().list_tiers(TIERS + ("founding",))}
    founding = rows.get("founding")
    return {
        "success": True,
        "rate_limit_per_hour": s["onboarding_rate_limit_per_hour"],
        "upload_window_minutes": s["onboarding_upload_window_minutes"],
        "max_file_mb": s["onboarding_max_file_mb"],
        "max_files_per_kind": s["onboarding_max_files_per_kind"],
        "max_dishes": s["onboarding_max_dishes"],
        "max_dish_price": s["onboarding_max_dish_price"],
        "max_preorder_days": s["onboarding_max_preorder_days"],
        "min_age": s["onboarding_min_age"],
        "review_days": s["onboarding_review_days"],
        "agreement_version": s["seller_agreement_version"],
        "min_id_validity_months": s["onboarding_min_id_validity_months"],
        "tiers": [
            {
                "tier": t,
                "commission_percent": _percent(rows[t]["commission_rate"]),
                "monthly_fee_vnd": _vnd(rows[t]["monthly_fee_vnd"]),
                "max_items": rows[t]["max_items"],
                "max_categories": rows[t]["max_categories"],
            }
            for t in TIERS if t in rows
        ],
        # Founding offer: rate + fee after the free months come from the founding plan row.
        "founding": {
            "slots": s["founding_slots"],
            "free_months": s["founding_free_months"],
            "commission_percent": _percent(founding["commission_rate"]) if founding else None,
            "monthly_fee_vnd": _vnd(founding["monthly_fee_vnd"]) if founding else None,
        },
        "enterprise": {
            "slots": s["enterprise_slots"],
            "taken": DAOSellerProfiles().count_sellers_by_tier("enterprise"),
        },
    }


@router.post("/applications")
def create_application(body: Schema.RequestCreateOnboardingApplication, request: Request):
    settings = _settings()
    ip = _client_ip(request)
    if _rate_limited(ip, settings["onboarding_rate_limit_per_hour"]):
        raise _error(429, "too_many_applications", "Too many applications, try again later")
    _verify_turnstile(body.turnstile_token, ip)

    if not body.agreed:
        raise _error(400, "agreement_required", "Please accept the Seller Agreement")
    if not body.personal_data_consent:
        raise _error(400, "consent_required", "Please accept the processing of your personal data")
    if body.agreement_version != settings["seller_agreement_version"]:
        raise _error(409, "agreement_outdated", "The Seller Agreement was updated, please reload the page")
    if not same_name(body.signature_name, body.first_name, body.last_name):
        raise _error(400, "signature_mismatch", "Type your full name exactly as above")

    required = ("first_name", "last_name", "nationality", "id_number", "residential_address",
                "store_name", "pickup_address", "bank_name", "bank_account_number", "bank_account_holder")
    for field in required:
        if not _squash(getattr(body, field)):
            raise _error(400, "missing_field", "Required field is empty", field=field)
    if body.tax_resident is None:
        raise _error(400, "missing_field", "Required field is empty", field="tax_resident")
    code = id_error(body.id_type, body.id_number, body.id_expiry_date, date.today(),
                    settings["onboarding_min_id_validity_months"])
    if code:
        raise _error(400, code, "Check the ID document", months=settings["onboarding_min_id_validity_months"])
    if not valid_bank_account(body.bank_account_number):
        raise _error(400, "invalid_bank_account", "Account number must be 6 to 20 digits")
    if not bank_holder_matches(body.bank_account_holder, body.first_name, body.last_name):
        raise _error(400, "bank_holder_mismatch", "The bank account must be in your own name")
    if body.tier not in TIERS:
        raise _error(400, "invalid_tier", "Invalid plan")
    if body.tier == "enterprise" and DAOSellerProfiles().count_sellers_by_tier("enterprise") >= settings["enterprise_slots"]:
        raise _error(409, "enterprise_full", "No Enterprise places left", slots=settings["enterprise_slots"])
    if not EMAIL_RE.match(body.email.strip()):
        raise _error(400, "invalid_email", "Invalid email")
    try:
        phone = to_e164_vn(body.phone)
    except ValueError:
        raise _error(400, "invalid_phone", "Invalid phone number")
    if age(body.date_of_birth, date.today()) < settings["onboarding_min_age"]:
        raise _error(400, "under_age", "Seller is under the minimum age", min_age=settings["onboarding_min_age"])
    maps_link = (body.maps_link or "").strip() or None
    if maps_link and not _is_maps_link(maps_link):
        raise _error(400, "invalid_maps_link", "Paste a Google Maps link")
    if body.opening_time and body.closing_time and body.opening_time >= body.closing_time:
        raise _error(400, "invalid_hours", "Opening time must be before closing time")

    dao = DAOOnboarding()
    limits = dao.get_tier_limits(body.tier)
    if limits is None:
        raise _error(400, "invalid_tier", "Invalid plan")
    menu = _clean_menu(body.menu, limits, settings)

    upload_token = secrets.token_urlsafe(32)
    row = dao.create_application({
        "status": "draft",
        "first_name": _squash(body.first_name),
        "last_name": _squash(body.last_name),
        "date_of_birth": body.date_of_birth.isoformat(),
        "nationality": _squash(body.nationality),
        "id_type": body.id_type,
        "id_number": _squash(body.id_number),
        "id_expiry_date": body.id_expiry_date.isoformat(),
        "email": body.email.strip(),
        "phone": phone,
        "residential_address": _squash(body.residential_address),
        "tax_code": _squash(body.tax_code or "") or None,
        "tax_resident": body.tax_resident,
        "store_name": _squash(body.store_name),
        "store_description": (body.store_description or "").strip() or None,
        "pickup_address": _squash(body.pickup_address),
        "maps_link": maps_link,
        "opening_time": body.opening_time.isoformat() if body.opening_time else None,
        "closing_time": body.closing_time.isoformat() if body.closing_time else None,
        "menu": menu,
        "tier": body.tier,
        "founding_invited": body.founding_invited,
        "bank_name": _squash(body.bank_name),
        "bank_account_number": _squash(body.bank_account_number).replace(" ", ""),
        "bank_account_holder": _squash(body.bank_account_holder),
        "agreement_version": str(body.agreement_version),
        "agreed_at": datetime.now(timezone.utc).isoformat(),
        "personal_data_consent_at": datetime.now(timezone.utc).isoformat(),
        "signature_name": _squash(body.signature_name),
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:500],
        "upload_token": upload_token,
    })
    _record_hit(ip)
    return {"success": True, "id": row["id"], "upload_token": upload_token}


@router.post("/applications/{application_id}/files")
def upload_file(
    application_id: str,
    body: Schema.RequestUploadOnboardingFile,
    x_upload_token: str = Header(default=None),
):
    settings = _settings()
    dao = DAOOnboarding()
    app = _load_draft(dao, application_id, x_upload_token, settings)

    if body.kind not in FILE_KINDS:
        raise _error(400, "invalid_file_kind", "Invalid document type")
    if body.kind == "id_document" and app.get("id_type") != "passport":
        # Vietnamese sellers give the ID number only (NĐ 356: no CCCD photos, eKYC later)
        raise _error(400, "id_document_not_needed", "Only a passport photo is needed")
    item_key = body.item_key if body.kind == "dish_photo" else None
    if body.kind == "dish_photo" and item_key not in {m["key"] for m in app["menu"]}:
        raise _error(400, "unknown_dish", "This dish is not in the menu")

    data = body.file_base64
    if data.startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        content = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise _error(400, "invalid_file", "Could not read the file")
    max_mb = settings["onboarding_max_file_mb"]
    if len(content) > max_mb * 1024 * 1024:
        raise _error(400, "file_too_large", "File is too large", mb=max_mb)
    content_type, ext = _sniff(content)
    if content_type is None or (body.kind == "dish_photo" and ext == "pdf"):
        raise _error(400, "invalid_file_type", "Use a JPG, PNG or PDF file")

    files = dao.list_files(application_id)
    if body.kind == "dish_photo":
        replaced = [f for f in files if f["kind"] == "dish_photo" and f["item_key"] == item_key]
    else:
        replaced = []
        limit = settings["onboarding_max_files_per_kind"]
        if sum(f["kind"] == body.kind for f in files) >= limit:
            raise _error(400, "too_many_files", "Too many files of this type", limit=limit)

    if ext != "pdf":
        content, content_type, ext = compress_to_jpeg(content), "image/jpeg", "jpg"
    path = f"{application_id}/{body.kind}-{uuid.uuid4()}.{ext}"
    upload_private(BUCKET, path, content, content_type)
    row = dao.create_file({
        "application_id": application_id,
        "kind": body.kind,
        "item_key": item_key,
        "storage_path": path,
        "content_type": content_type,
        "size_bytes": len(content),
    })
    # New photo for the same dish: drop the old one only after the new one is stored.
    for old in replaced:
        dao.delete_file(old["id"])
        try:
            remove_private(BUCKET, old["storage_path"])
        except Exception as e:
            logger.warning(f"[Onboarding] could not remove {old['storage_path']}: {repr(e)}")
    return {"success": True, "file_id": row["id"]}


@router.post("/applications/{application_id}/submit")
def submit_application(application_id: str, x_upload_token: str = Header(default=None)):
    dao = DAOOnboarding()
    app = _load_draft(dao, application_id, x_upload_token, _settings())

    files = dao.list_files(application_id)
    if app.get("id_type") == "passport" and not any(f["kind"] == "id_document" for f in files):
        raise _error(400, "id_document_required", "Upload your passport photo page")
    photos = {f["item_key"] for f in files if f["kind"] == "dish_photo"}
    missing = [m["key"] for m in app["menu"] if m["key"] not in photos]
    if missing:
        raise _error(400, "dish_photo_missing", "Some dishes have no photo", keys=missing)

    if not dao.submit(application_id):
        raise _error(404, "application_not_found", "Application not found or expired")
    return {"success": True, "reference": application_id[:8].upper()}
