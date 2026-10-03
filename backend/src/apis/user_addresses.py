import logging

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
)

from core.auth import verify_token
from core.phone import to_e164_vn
from dao.v2.dao_user_addresses import DAOUserAddresses
from schemas import Schema

router = APIRouter(prefix="/user_addresses")
logger = logging.getLogger(__name__)


def normalize_phone(data: dict) -> None:
    if "phone_number" in data:
        try:
            data["phone_number"] = to_e164_vn(data["phone_number"])
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid phone number")


@router.get("")
def list_user_addresses(user=Depends(verify_token)):
    try:
        addresses = DAOUserAddresses().read_addresses(user["id"])
        return {"success": True, "addresses": addresses}
    except Exception as e:
        logger.exception(f"Exception in GET /user_addresses: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )


@router.post("")
def create_user_address(body: Schema.RequestCreateUserAddress, user=Depends(verify_token)):
    user_id = user["id"]
    data = body.model_dump()
    normalize_phone(data)

    try:
        dao = DAOUserAddresses()
        # A user's first address is always the default, so there is never zero.
        if not dao.has_address(user_id):
            data["is_default"] = True
        if data["is_default"]:
            dao.clear_default(user_id)

        address = dao.create_address(user_id, data)
        return {"success": True, "address": address}
    except Exception as e:
        logger.exception(f"Exception in POST /user_addresses: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )


@router.patch("/{address_id}")
def update_user_address(address_id: int, body: Schema.RequestUpdateUserAddress, user=Depends(verify_token)):
    user_id = user["id"]
    # exclude_unset (not exclude_none) so an explicit null clears `note`.
    data = body.model_dump(exclude_unset=True)
    normalize_phone(data)

    dao = DAOUserAddresses()
    try:
        existing = dao.read_address(user_id, address_id)
    except Exception as e:
        logger.exception(f"Exception in PATCH /user_addresses/{address_id}: {repr(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{repr(e)}")

    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    # Unsetting the default directly would leave the user with none; the way to
    # move it is to set another address as default.
    if data.get("is_default") is False and existing["is_default"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unset the default address; set another address as default instead",
        )

    if not data:
        return {"success": True, "address": existing}

    try:
        if data.get("is_default"):
            dao.clear_default(user_id, except_id=address_id)

        address = dao.update_address(user_id, address_id, data)
        return {"success": True, "address": address}
    except Exception as e:
        logger.exception(f"Exception in PATCH /user_addresses/{address_id}: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )
