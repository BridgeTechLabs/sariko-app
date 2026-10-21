"""T35: complaints in the app, tied to an order (docs/dev/complaints/README.md, đề án II.2.4 d, II.3 h, III.1 c).
Buyer or seller of a paid order files one; it gets a tracking code and a status the sender follows here.
The admin app moves the status and records the outcome. Photos go to the private "complaints" bucket,
one request per photo (nginx caps a request at 10 MB)."""
import base64
import binascii
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from apis.onboarding import _error, _sniff
from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_complaints import ComplaintOpenExists, DAOComplaints
from schemas import Schema
from services import push_service
from utils.storage import compress_to_jpeg, signed_url, upload_private

router = APIRouter(prefix="/complaints")
logger = logging.getLogger(__name__)

BUCKET = "complaints"
CATEGORIES = {
    "buyer": ["wrong_item", "damaged", "missing_item", "late", "other"],
    "seller": ["buyer_issue", "delivery_issue", "payment_issue", "other"],
}
MAX_LENGTH = 2000            # description length: an input format check, not a business parameter
ENDED = ("done", "cancelled", "delivery_failed")
SIGNED_URL_SECONDS = 600
SETTINGS_DEFAULTS = {"complaint_window_hours": 24, "complaint_max_images": 3, "onboarding_max_file_mb": 5,
                     "complaint_ack_hours": 24, "complaint_resolve_working_days": 7}


def _settings() -> dict:
    return DAOAdminConfig().get_positive_ints(SETTINGS_DEFAULTS)


def sender_role(order: dict, user_id: str) -> Optional[str]:
    if order.get("user_id") == user_id:
        return "buyer"
    if (order.get("seller_profiles") or {}).get("user_id") == user_id:
        return "seller"
    return None


def block_reason(order: dict, window_hours: int, now: Optional[datetime] = None) -> Optional[str]:
    """Why this order cannot get a complaint in the app now (Q3), or None. An open order always can;
    an ended one only within complaint_window_hours of status_changed_at."""
    if order.get("payment_status") != "paid":
        return "order_not_paid"
    if order.get("status") in ENDED:
        ended = datetime.fromisoformat(order["status_changed_at"])
        if (now or datetime.now(timezone.utc)) - ended > timedelta(hours=window_hours):
            return "window_closed"
    return None


def summary(row: dict, user_id: str) -> dict:
    """A complaint as the order screens list it."""
    return {k: row[k] for k in ("id", "code", "sender_role", "category", "status", "resolution", "created_at",
                                "resolved_at")} | {"is_mine": row["user_id"] == user_id}


def complaints_for_order(order: dict, user_id: str, role: str) -> dict:
    """complaints + can_complain for an order detail response. A buyer sees their own complaints, the
    seller sees the buyer's and their own (Q9). A failure here must not break the order screen."""
    try:
        rows = [r for r in DAOComplaints().list_for_order(order["id"]) if role == "seller" or r["user_id"] == user_id]
        open_mine = any(r["user_id"] == user_id and r["status"] != "resolved" for r in rows)
        can = not open_mine and block_reason(order, DAOAdminConfig().get_positive_int("complaint_window_hours", 24)) is None
        return {"complaints": [summary(r, user_id) for r in rows], "can_complain": can}
    except Exception as e:
        logger.error(f"[Complaint] order {order.get('id')} complaints not loaded: {repr(e)}")
        return {"complaints": [], "can_complain": False}


@router.get("/config")
def get_config():
    s = _settings()
    return {"success": True, "window_hours": s["complaint_window_hours"], "max_images": s["complaint_max_images"],
            "max_file_mb": s["onboarding_max_file_mb"], "max_length": MAX_LENGTH, "categories": CATEGORIES,
            "ack_hours": s["complaint_ack_hours"], "resolve_working_days": s["complaint_resolve_working_days"]}


@router.post("")
def create_complaint(body: Schema.RequestCreateComplaint, user=Depends(verify_token)):
    dao = DAOComplaints()
    order = dao.read_order(body.order_id)
    if not order:
        raise _error(404, "order_not_found", "Order not found")
    role = sender_role(order, user["id"])
    if not role:
        raise _error(403, "not_your_order", "This is not your order")
    s = _settings()
    reason = block_reason(order, s["complaint_window_hours"])
    if reason:
        raise _error(400, reason, "This order cannot get a complaint now", hours=s["complaint_window_hours"])
    if body.category not in CATEGORIES[role]:
        raise _error(400, "invalid_category", "Choose a complaint type", field="category")
    description = body.description.strip()
    if not description:
        raise _error(400, "missing_field", "Describe the problem", field="description")
    if len(description) > MAX_LENGTH:
        raise _error(400, "description_too_long", "The description is too long", field="description", max=MAX_LENGTH)
    try:
        row = dao.create(order["id"], user["id"], role, body.category, description)
    except ComplaintOpenExists:
        raise _error(409, "complaint_open", "You already have an open complaint on this order")
    if role == "buyer":
        push_service.notify_seller_complaint((order.get("seller_profiles") or {}).get("user_id"), order["id"])
    push_service.notify_admins("admin_new_complaint", f"/complaints?open={row['id']}", code=row["code"], category=body.category)
    logger.warning(f"[Complaint] {row['code']} order={order['id']} role={role} held={row['held_payout']}")
    return {"success": True, "complaint": {"id": row["id"], "code": row["code"], "status": row["status"]}}


@router.post("/{complaint_id}/images")
def upload_image(complaint_id: str, body: Schema.RequestUploadImage, user=Depends(verify_token)):
    dao = DAOComplaints()
    row = dao.read(complaint_id)
    if not row or row["user_id"] != user["id"]:
        raise _error(404, "complaint_not_found", "Complaint not found")
    if row["status"] == "resolved":
        raise _error(400, "complaint_closed", "This complaint is already resolved")
    s = _settings()
    paths = row["image_paths"] or []
    if len(paths) >= s["complaint_max_images"]:
        raise _error(400, "too_many_images", "Too many photos", max=s["complaint_max_images"])
    data = body.image_base64.split(",", 1)[1] if body.image_base64.startswith("data:") else body.image_base64
    try:
        content = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise _error(400, "invalid_file", "Could not read the file")
    if len(content) > s["onboarding_max_file_mb"] * 1024 * 1024:
        raise _error(400, "file_too_large", "File is too large", mb=s["onboarding_max_file_mb"])
    if _sniff(content)[1] not in ("jpg", "png"):
        raise _error(400, "invalid_file_type", "Use a JPG or PNG photo")
    path = f"{complaint_id}/{len(paths) + 1}.jpg"
    upload_private(BUCKET, path, compress_to_jpeg(content), "image/jpeg")
    dao.set_image_paths(complaint_id, paths + [path])
    return {"success": True, "image_count": len(paths) + 1}


@router.get("/mine")
def list_mine(user=Depends(verify_token)):
    rows = DAOComplaints().list_by_user(user["id"])
    return {"success": True, "complaints": [summary(r, user["id"]) | {"order_id": r["order_id"]} for r in rows]}


@router.get("/{complaint_id}")
def get_complaint(complaint_id: str, user=Depends(verify_token)):
    """The sender, or the seller of the order (Q9), sees the complaint with its photos."""
    dao = DAOComplaints()
    row = dao.read(complaint_id)
    order = dao.read_order(row["order_id"]) if row else None
    if not row or (row["user_id"] != user["id"] and sender_role(order or {}, user["id"]) != "seller"):
        raise _error(404, "complaint_not_found", "Complaint not found")
    images = [signed_url(BUCKET, p, SIGNED_URL_SECONDS) for p in row["image_paths"] or []]
    detail = {k: v for k, v in row.items() if k not in ("user_id", "image_paths")}
    return {"success": True, "complaint": detail | {"is_mine": row["user_id"] == user["id"], "images": images}}
