"""Admin Gateway: endpoints the admin backend (separate repo) calls with header X-Api-Key = ADMIN_GATEWAY_API_KEY
(T176, docs/dev/20261110-admin-cancel-notify). The key unset or empty turns the gateway off (503): an empty key never
matches. Not in the public /docs. The app trusts nothing but the key: it reads the order itself."""
import hmac
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from apis import onboarding as join, sellers, seller_profile_completion as spc
from core.seller_kyc import bank_holder_matches, squash
from dao.dao_admin_payouts import DAOAdminPayouts
from dao.dao_orders import DAOOrders
from dao.dao_seller_profile_completion import DAOSellerProfileCompletion
from schemas import Schema
from services import push_service
from utils.storage import remove_private, signed_url

logger = logging.getLogger(__name__)


def verify_gateway_key(x_api_key: str = Header(default="")):
    key = os.getenv("ADMIN_GATEWAY_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Admin Gateway is off")
    if not hmac.compare_digest(x_api_key.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


router = APIRouter(prefix="/admin-gateway", dependencies=[Depends(verify_gateway_key)], include_in_schema=False)


@router.post("/orders/{order_id}/cancelled-notify")
def cancelled_notify(order_id: UUID):
    """A4: an admin cancelled this order (admin repo apis/orders.py); push the buyer and, for a paid order, the seller
    like the app's own cancels do. Calling it twice pushes twice (QĐ B: accepted, rare)."""
    order_id = str(order_id)
    dao = DAOOrders()
    order = dao.read_order_by_id_raw(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] != "cancelled":
        raise HTTPException(status_code=409, detail="Order is not cancelled")
    was_done = any(h["status"] == "done" for h in dao.read_status_history(order_id))
    push_service.notify_admin_cancelled(
        order, was_done, charged=was_done and DAOAdminPayouts().has_deduction_for_order(order_id))
    logger.warning(f"[AdminGateway] cancel of order={order_id} pushed (paid={order['payment_status']}, done={was_done})")
    return {"success": True}


# ── Menu edits (T-admin-menu-edit, docs/dev/20261114-admin-menu-edit): an admin edits a store's option groups and
# a dish's fields (stock, minimum per order...) through the seller routes' own code, with the seller_id of the path:
# the same rules, limits and checks, and a dish / group of another store answers 404 like it does for that store's
# seller. The admin backend has its own admin login; here the key is all there is.

def _menu_edit(what: str, seller_id: UUID, edit, *args):
    result = edit(str(seller_id), *args)
    logger.warning(f"admin edit seller={seller_id} {what}")   # warning: main.py logs from WARNING up, as the cancel push does
    return result


@router.patch("/sellers/{seller_id}/menu/items/{item_id}")
def edit_dish(seller_id: UUID, item_id: UUID, body: Schema.RequestUpdateFoodItem):
    return _menu_edit(f"dish={item_id} fields={sorted(body.model_fields_set)}", seller_id, sellers.update_food_item_for, str(item_id), body)


@router.post("/sellers/{seller_id}/menu/items/{item_id}/option-groups")
def create_option_group(seller_id: UUID, item_id: UUID, body: Schema.RequestOptionGroup):
    return _menu_edit(f"new option group on dish={item_id}", seller_id, sellers.create_option_group_for, str(item_id), body)


@router.put("/sellers/{seller_id}/menu/items/{item_id}/option-groups")
def order_option_groups(seller_id: UUID, item_id: UUID, body: Schema.RequestDishGroupOrder):
    return _menu_edit(f"option group order on dish={item_id}", seller_id, sellers.order_option_groups_for, str(item_id), body)


@router.post("/sellers/{seller_id}/menu/items/{item_id}/option-groups/{group_id}")
def attach_option_group(seller_id: UUID, item_id: UUID, group_id: UUID):
    return _menu_edit(f"attach group={group_id} to dish={item_id}", seller_id, sellers.attach_option_group_for, str(item_id), str(group_id))


@router.delete("/sellers/{seller_id}/menu/items/{item_id}/option-groups/{group_id}")
def detach_option_group(seller_id: UUID, item_id: UUID, group_id: UUID):
    return _menu_edit(f"detach group={group_id} from dish={item_id}", seller_id, sellers.detach_option_group_for, str(item_id), str(group_id))


@router.put("/sellers/{seller_id}/menu/option-groups/{group_id}")
def update_option_group(seller_id: UUID, group_id: UUID, body: Schema.RequestOptionGroup):
    return _menu_edit(f"option group={group_id}", seller_id, sellers.update_option_group_for, str(group_id), body)


@router.delete("/sellers/{seller_id}/menu/option-groups/{group_id}")
def delete_option_group(seller_id: UUID, group_id: UUID):
    return _menu_edit(f"delete option group={group_id}", seller_id, sellers.delete_option_group_for, str(group_id))


# ── Seller KYC (docs/dev/20261124-seller-kyc-admin): an operator fills in a seller's ID, tax and bank with the seller
# form's own checks (spc.check_kyc), adds / deletes passport photos, and sees the agreement (never signs it). The
# application status is never changed (QĐ-3). Responses carry the full ID / account numbers: the admin app shows them
# to operators, as its applications page does. Logs carry field names, never values.

SIGNED_URL_SECONDS = 600   # passport photo links, as the admin applications page


def _seller(dao, seller_id: UUID) -> dict:
    seller = dao.read_seller(str(seller_id), "id")
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    return seller


def _photo_url(path: str):
    try:
        return signed_url(join.BUCKET, path, SIGNED_URL_SECONDS)
    except Exception as e:   # object gone: the photo still shows, without a link
        logger.error(f"[AdminGateway] no link for a passport photo: {type(e).__name__}")
        return None


def _kyc(dao, seller: dict, settings: dict) -> dict:
    app = dao.read_application(seller["id"]) or {}
    files = dao.list_id_documents(app["id"]) if app else []
    return {
        "success": True,
        "status": app.get("status"),   # None = no application yet
        "identity": {
            **{f: app.get(f) for f in spc.IDENTITY_FIELDS},
            "email": app.get("email") or dao.read_user_email(seller["user_id"]) or "",
        },
        # tax_resident as the payouts read it; the application has the same value (both written together)
        "tax": {"tax_resident": seller.get("tax_resident"), "tax_code": app.get("tax_code") or ""},
        "bank": {f: seller.get(f) for f in spc.BANK_FIELDS},
        "agreement": {
            **{f: app.get(f) for f in ("agreement_version", "agreed_at", "signature_name", "personal_data_consent_at")},
            "version_current": settings["seller_agreement_version"],
        },
        "id_documents": [{"id": f["id"], "content_type": f["content_type"], "url": _photo_url(f["storage_path"])}
                         for f in files],
        "limits": spc.limits(settings),
    }


@router.get("/sellers/{seller_id}/kyc")
def read_kyc(seller_id: UUID):
    dao = DAOSellerProfileCompletion()
    return _kyc(dao, _seller(dao, seller_id), spc._settings())


@router.put("/sellers/{seller_id}/kyc")
def save_kyc(seller_id: UUID, body: Schema.RequestAdminSellerKyc):
    settings = spc._settings()
    dao = DAOSellerProfileCompletion()
    seller = _seller(dao, seller_id)
    app = dao.read_application(seller["id"])
    if not (body.identity or body.tax or body.bank):
        raise spc._error(400, "nothing_to_save", "Nothing to save")
    if not app and not body.identity:
        # No full name yet: whose account it is cannot be checked (QĐ-11), and a tax-only row would be half-filled.
        if body.bank:
            raise spc._error(409, "identity_required", "Save the ID details first")
        raise spc._error(400, "missing_group", "Fill in every missing section", groups=["identity"])

    app_data, seller_data = spc.check_kyc(body, app, seller, settings)
    old_name = (app or {}).get("full_name") or ""
    name = app_data.get("full_name") or old_name
    holder = seller_data.get("bank_account_holder") or seller.get("bank_account_holder")
    # QĐ-4: an identity save checks the holder only when an earlier name really changes (the first save never: a holder
    # already off is fixed on the bank card next); a bank save always does.
    name_changed = bool(old_name) and squash(name).casefold() != squash(old_name).casefold()
    if (body.bank or name_changed) and holder and not bank_holder_matches(holder, name):
        raise spc._error(400, "bank_holder_mismatch", "The bank account must be in the seller's own name")
    changed = sorted({f for f, v in app_data.items() if (app or {}).get(f) != v}
                     | {f for f, v in seller_data.items() if seller.get(f) != v})

    final = {**seller, **seller_data}
    snapshot = {"phone": final["phone"], "pickup_address": final["address"], **{f: final[f] for f in spc.BANK_FIELDS}}
    try:
        if app:
            # null never overwrites a /join row's value (its CHECK keeps those columns filled)
            dao.update_application(app["id"], {**app_data, **{k: v for k, v in snapshot.items() if v is not None}})
        else:
            # Agreement columns stay null: the seller signs in the app (QĐ-3, QĐ-6).
            dao.create_application({
                **app_data, **snapshot,
                "source": "existing_seller",
                "seller_profile_id": seller["id"],
                "status": "approved",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "email": app_data.get("email") or dao.read_user_email(seller["user_id"]) or "",
                "store_name": seller.get("store_name") or "",
                "tier": seller["tier"],
                "menu": [],
            })
        if seller_data:
            dao.update_seller(seller["id"], seller_data)
    except Exception as e:
        # The DB error text can quote the row (ID number, account): log the type only.
        logger.error(f"[AdminGateway] kyc save failed for seller={seller_id}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Could not save, please try again")
    logger.warning(f"admin edit seller={seller_id} kyc fields={changed}")
    return {**_kyc(dao, dao.read_seller(seller["id"], "id"), settings), "changed": changed}


@router.post("/sellers/{seller_id}/kyc/files")
def upload_kyc_file(seller_id: UUID, body: Schema.RequestUploadOnboardingFile):
    settings = spc._settings()
    dao = DAOSellerProfileCompletion()
    seller = _seller(dao, seller_id)
    app = dao.read_application(seller["id"])
    row = spc.store_id_document(dao, app, dao.count_id_documents(app["id"]) if app else 0, body, settings)
    logger.warning(f"admin edit seller={seller_id} kyc photo={row['id']} added")
    return {**_kyc(dao, seller, settings), "file_id": row["id"]}


@router.delete("/sellers/{seller_id}/kyc/files/{file_id}")
def delete_kyc_file(seller_id: UUID, file_id: UUID):
    """A passport photo of this seller's application only. Storage first, then the row: a delete that stopped
    half-way (object gone, row left) runs again fine, since removing a missing object is not an error."""
    dao = DAOSellerProfileCompletion()
    seller = _seller(dao, seller_id)
    app = dao.read_application(seller["id"])
    photo = next((f for f in dao.list_id_documents(app["id"]) if f["id"] == str(file_id)), None) if app else None
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    remove_private(join.BUCKET, photo["storage_path"])
    dao.delete_file(photo["id"])
    logger.warning(f"admin edit seller={seller_id} kyc photo={file_id} deleted")
    return _kyc(dao, seller, spc._settings())
