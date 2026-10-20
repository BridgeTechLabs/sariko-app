"""Existing sellers complete their seller profile (spec docs/dev/seller-profile-completion).

GET tells the app which groups are missing (banner on Today, dot on Me, the form shows only
those); POST saves them with the /join rules. Identity / tax / agreement go into an
onboarding_applications row (source existing_seller) linked to the seller; bank, phone and
pickup address go straight into seller_profiles, where payouts and Lalamove read them.
Personal data never goes to the logs: errors carry a code, not the values.
"""
import base64
import binascii
import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from apis import onboarding as join
from core.auth import verify_token
from core.phone import to_e164_vn
from core.seller_kyc import age, bank_holder_matches, id_error, mask, same_name, squash, valid_bank_account
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_seller_profile_completion import DAOSellerProfileCompletion
from schemas import Schema
from utils.storage import compress_to_jpeg, upload_private

router = APIRouter(prefix="/sellers/me/profile-completion")
logger = logging.getLogger(__name__)

GROUPS = ("identity", "id_document", "tax", "bank", "phone", "pickup_address", "agreement")
IDENTITY_FIELDS = ("first_name", "last_name", "date_of_birth", "nationality", "id_type", "id_number",
                   "id_expiry_date", "residential_address")
BANK_FIELDS = ("bank_name", "bank_account_number", "bank_account_holder")
DONE_STATUSES = ("submitted", "approved")
SETTINGS_DEFAULTS = {**join.SETTINGS_DEFAULTS, "onboarding_min_id_validity_months": 6}
_error = join._error


def _settings() -> dict:
    return DAOAdminConfig().get_positive_ints(SETTINGS_DEFAULTS)


def missing_groups(seller: dict, app, id_documents: int, agreement_version: int) -> list:
    """The one place that decides what is missing (banner, Me dot and form all use it)."""
    app = app or {}
    missing = []
    if app.get("status") not in DONE_STATUSES or not all(app.get(f) for f in IDENTITY_FIELDS):
        missing.append("identity")
    if app.get("id_type") == "passport" and id_documents == 0:   # Q6: no CCCD photo for Vietnamese sellers
        missing.append("id_document")
    if app.get("tax_resident") is None:
        missing.append("tax")
    if not all(seller.get(f) for f in BANK_FIELDS) or (
        # Q12: an account in someone else's name counts as missing
        app.get("first_name") and not bank_holder_matches(seller["bank_account_holder"], app["first_name"], app["last_name"])
    ):
        missing.append("bank")
    if not seller.get("phone"):
        missing.append("phone")
    if not seller.get("address") or seller.get("lat") is None or seller.get("lon") is None:
        missing.append("pickup_address")
    if str(app.get("agreement_version")) != str(agreement_version) or not app.get("personal_data_consent_at"):
        missing.append("agreement")
    return missing


def _load(user):
    dao = DAOSellerProfileCompletion()
    seller = dao.read_seller(user["id"])
    if not seller:
        raise HTTPException(status_code=403, detail="User is not a seller")
    app = dao.read_application(seller["id"])
    id_documents = dao.count_id_documents(app["id"]) if app else 0
    return dao, seller, app, id_documents


def _state(dao, user, seller, app, id_documents, settings) -> dict:
    app = app or {}
    missing = missing_groups(seller, app, id_documents, settings["seller_agreement_version"])
    return {
        "success": True,
        "complete": not missing,
        "missing": missing,
        "agreement_version_current": settings["seller_agreement_version"],
        "limits": {
            "min_age": settings["onboarding_min_age"],
            "min_id_validity_months": settings["onboarding_min_id_validity_months"],
            "max_file_mb": settings["onboarding_max_file_mb"],
            "max_files_per_kind": settings["onboarding_max_files_per_kind"],
        },
        "id_document_files": id_documents,
        # Owner-only. ID and account numbers come back masked; an empty field on save keeps them.
        "prefill": {
            "first_name": app.get("first_name") or "",
            "last_name": app.get("last_name") or "",
            "date_of_birth": app.get("date_of_birth"),
            "nationality": app.get("nationality") or "",
            "id_type": app.get("id_type") or "",
            "id_number_masked": mask(app.get("id_number")),
            "id_expiry_date": app.get("id_expiry_date"),
            "residential_address": app.get("residential_address") or "",
            "email": app.get("email") or dao.read_user_email(user["id"]) or "",
            "tax_resident": app.get("tax_resident"),
            "tax_code": app.get("tax_code") or "",
            "bank_name": seller.get("bank_name") or "",
            "bank_account_number_masked": mask(seller.get("bank_account_number")),
            "bank_account_holder": seller.get("bank_account_holder") or "",
            "phone": seller.get("phone") or "",
            "address": seller.get("address") or "",
            "lat": seller.get("lat"),
            "lon": seller.get("lon"),
        },
    }


@router.get("")
def get_profile_completion(user=Depends(verify_token)):
    dao, seller, app, id_documents = _load(user)
    return _state(dao, user, seller, app, id_documents, _settings())


def _new_value(value) -> str:
    """A typed ID / account number; empty or the masked one sent back = keep the stored one."""
    value = squash(value or "")
    return "" if "•" in value else value


def _required(value, field):
    if not squash(value or ""):
        raise _error(400, "missing_field", "Required field is empty", field=field)
    return squash(value)


@router.post("")
def save_profile_completion(body: Schema.RequestSellerProfileCompletion, request: Request, user=Depends(verify_token)):
    settings = _settings()
    dao, seller, app, id_documents = _load(user)
    version = settings["seller_agreement_version"]

    # The form sends every missing group at once (id_document is a separate upload), so an
    # application row is never created half-filled.
    sent = {g for g in GROUPS if getattr(body, g, None) is not None}
    lacking = [g for g in missing_groups(seller, app, id_documents, version) if g != "id_document" and g not in sent]
    if lacking:
        raise _error(400, "missing_group", "Fill in every missing section", groups=lacking)
    if not sent:
        raise _error(400, "nothing_to_save", "Nothing to save")

    # 1. Check everything before writing anything.
    app_data, seller_data = {}, {}
    today = date.today()
    if body.identity:
        i = body.identity
        id_number = _new_value(i.id_number) or (app or {}).get("id_number") or ""
        app_data.update(
            first_name=_required(i.first_name, "first_name"),
            last_name=_required(i.last_name, "last_name"),
            nationality=_required(i.nationality, "nationality"),
            residential_address=_required(i.residential_address, "residential_address"),
            id_type=i.id_type,
            id_number=id_number,
        )
        if i.date_of_birth is None:
            raise _error(400, "missing_field", "Required field is empty", field="date_of_birth")
        if age(i.date_of_birth, today) < settings["onboarding_min_age"]:
            raise _error(400, "under_age", "Seller is under the minimum age", min_age=settings["onboarding_min_age"])
        code = id_error(i.id_type, id_number, i.id_expiry_date, today, settings["onboarding_min_id_validity_months"])
        if code:
            raise _error(400, code, "Check the ID document", months=settings["onboarding_min_id_validity_months"])
        email = (i.email or "").strip()
        if email and not join.EMAIL_RE.match(email):
            raise _error(400, "invalid_email", "Invalid email")
        app_data.update(date_of_birth=i.date_of_birth.isoformat(), id_expiry_date=i.id_expiry_date.isoformat())
        if email:
            app_data["email"] = email
    if body.tax:
        if body.tax.tax_resident is None:
            raise _error(400, "missing_field", "Required field is empty", field="tax_resident")
        app_data.update(tax_resident=body.tax.tax_resident, tax_code=squash(body.tax.tax_code or "") or None)
    if body.bank:
        number = _new_value(body.bank.bank_account_number).replace(" ", "") or seller.get("bank_account_number") or ""
        if not valid_bank_account(number):
            raise _error(400, "invalid_bank_account", "Account number must be 6 to 20 digits")
        seller_data.update(
            bank_name=_required(body.bank.bank_name, "bank_name"),
            bank_account_number=number,
            bank_account_holder=_required(body.bank.bank_account_holder, "bank_account_holder"),
        )
    if body.phone is not None:
        try:
            seller_data["phone"] = to_e164_vn(body.phone)
        except ValueError:
            raise _error(400, "invalid_phone", "Invalid phone number")
    if body.pickup_address:
        p = body.pickup_address
        if p.lat is None or p.lon is None or not (-90 <= p.lat <= 90 and -180 <= p.lon <= 180):
            raise _error(400, "invalid_location", "Pick the pickup address on the map")
        seller_data.update(address=_required(p.address, "address"), lat=p.lat, lon=p.lon)

    first = app_data.get("first_name") or (app or {}).get("first_name") or ""
    last = app_data.get("last_name") or (app or {}).get("last_name") or ""
    if body.agreement:
        a = body.agreement
        if not a.agreed:
            raise _error(400, "agreement_required", "Please accept the Seller Agreement")
        if not a.personal_data_consent:
            raise _error(400, "consent_required", "Please accept the processing of your personal data")
        if a.agreement_version != version:
            raise _error(409, "agreement_outdated", "The Seller Agreement was updated, please reload the page")
        if not same_name(a.signature_name, first, last):
            raise _error(400, "signature_mismatch", "Type your full name exactly as above")
        now = datetime.now(timezone.utc).isoformat()
        app_data.update(agreement_version=str(version), agreed_at=now, personal_data_consent_at=now,
                        signature_name=squash(a.signature_name),
                        ip=join._client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:500])
    holder = seller_data.get("bank_account_holder") or seller.get("bank_account_holder")
    if (body.bank or body.identity) and first and holder and not bank_holder_matches(holder, first, last):
        raise _error(400, "bank_holder_mismatch", "The bank account must be in your own name")

    # 2. Write: the application row first (it has the constraints), then seller_profiles.
    final = {**seller, **seller_data}
    snapshot = {"phone": final["phone"], "pickup_address": final["address"],
                **{f: final[f] for f in BANK_FIELDS}}
    try:
        if app:
            update = {**app_data, **snapshot}
            if body.identity and app["status"] != "submitted":
                # Q13: changed identity goes back to review (also after needs_info / rejected)
                update.update(status="submitted", submitted_at=datetime.now(timezone.utc).isoformat())
            dao.update_application(app["id"], update)
        elif app_data:
            dao.create_application({
                **app_data, **snapshot,
                "source": "existing_seller",
                "seller_profile_id": seller["id"],
                "status": "submitted",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "email": app_data.get("email") or dao.read_user_email(user["id"]) or "",
                "store_name": seller.get("store_name") or "",
                "tier": seller["tier"],
                "menu": [],
            })
        if seller_data:
            dao.update_seller(seller["id"], seller_data)
    except Exception as e:
        # The DB error text can quote the row (ID number, account): log the type only.
        logger.error(f"[ProfileCompletion] save failed for seller {seller['id']}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Could not save, please try again")

    dao, seller, app, id_documents = _load(user)
    return _state(dao, user, seller, app, id_documents, settings)


@router.post("/files")
def upload_id_document(body: Schema.RequestUploadOnboardingFile, user=Depends(verify_token)):
    """Passport photo of a foreign seller. Vietnamese sellers give the ID number only (Q6)."""
    settings = _settings()
    dao, seller, app, id_documents = _load(user)
    if body.kind != "id_document":
        raise _error(400, "invalid_file_kind", "Invalid document type")
    if not app:
        raise _error(409, "identity_required", "Save your identity first")
    if app.get("id_type") != "passport":
        raise _error(400, "id_document_not_needed", "Only a passport photo is needed")
    limit = settings["onboarding_max_files_per_kind"]
    if id_documents >= limit:
        raise _error(400, "too_many_files", "Too many files of this type", limit=limit)

    data = body.file_base64.split(",", 1)[1] if body.file_base64.startswith("data:") else body.file_base64
    try:
        content = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise _error(400, "invalid_file", "Could not read the file")
    max_mb = settings["onboarding_max_file_mb"]
    if len(content) > max_mb * 1024 * 1024:
        raise _error(400, "file_too_large", "File is too large", mb=max_mb)
    content_type, ext = join._sniff(content)
    if content_type is None:
        raise _error(400, "invalid_file_type", "Use a JPG, PNG or PDF file")
    if ext != "pdf":
        content, content_type, ext = compress_to_jpeg(content), "image/jpeg", "jpg"

    path = f"{app['id']}/id_document-{uuid.uuid4()}.{ext}"
    upload_private(join.BUCKET, path, content, content_type)
    dao.create_file({"application_id": app["id"], "kind": "id_document", "item_key": None,
                     "storage_path": path, "content_type": content_type, "size_bytes": len(content)})
    dao, seller, app, id_documents = _load(user)
    return _state(dao, user, seller, app, id_documents, settings)
