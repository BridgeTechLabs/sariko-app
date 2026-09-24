import datetime
import uuid
import traceback
from typing import List, Optional
import json
import logging

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
    Query, 
    Response
)

import time

from core.auth import verify_token
from dao.dao_users import DAOUsers
from dao.dao_seller_profiles import DAOSellerProfiles
from dao.dao_user_addresses import DAOUserAddresses
from schemas import Schema
from utils.storage import upload_image_base64

router = APIRouter(prefix="/users")
logger = logging.getLogger(__name__)


@router.get("/info/me")
def get_current_user_profile(user=Depends(verify_token)):
    try:
        dao_users = DAOUsers()
        users = dao_users.get_users(user_id=user["id"])
        if users and users.get("is_seller"):
            dao = DAOSellerProfiles()
            profile = dao.read_seller_profile_by_user_id(user["id"])
            if profile:
                users.update({"seller_id": profile["id"]})
                if profile.get("avatar_url"):
                    users["avatar_url"] = profile["avatar_url"]
                if profile.get("phone"):
                    users["phone"] = profile["phone"]

        return {"success": True , "user": users}
    
    except HTTPException as e:
        logger.exception(f"Exception in /users/me: {repr(e)}")
        if e.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token - {repr(e)}",
            )
    
    except Exception as e:
        logger.exception(f"Exception in /users/me: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )
        
        
@router.patch("/me/profile")
def update_current_user_profile(body: Schema.RequestUpdateProfile, user=Depends(verify_token)):
    try:
        user_id = user["id"]
        dao_users = DAOUsers()
        dao_seller = DAOSellerProfiles()
        data = body.model_dump(exclude_none=True)

        seller_profile = dao_seller.read_seller_profile_by_user_id(user_id)
        is_seller = seller_profile is not None

        if data.get("avatar_url") and is_seller:
            dao_seller.update_avatar_url(user_id, data.pop("avatar_url"))

        if is_seller:
            seller_fields = {}
            for field in ("phone", "address", "lat", "lon"):
                if field in data:
                    seller_fields[field] = data.pop(field)
            data.pop("address_details", None)
            if seller_fields:
                dao_seller.update_seller_profile_info(user_id, seller_fields)
        else:
            if body.address:
                dao_addresses = DAOUserAddresses()
                dao_addresses.upsert_default_address(
                    user_id=user_id,
                    address=body.address,
                    address_details=body.address_details,
                    lat=body.lat,
                    lon=body.lon,
                )
            for field in ("address", "address_details", "lat", "lon"):
                data.pop(field, None)

        updated_user = dao_users.update_user_profile(user_id, data)

        return {"success": True, "user": updated_user}

    except Exception as e:
        logger.exception(f"Exception in PATCH /users/me/profile: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )


@router.post("/me/avatar")
def upload_avatar(body: Schema.RequestUploadImage, user=Depends(verify_token)):
    try:
        user_id = user["id"]
        seller_profile = DAOSellerProfiles().read_seller_profile_by_user_id(user_id)
        if seller_profile:
            path = f"avatar-sellers/{seller_profile['id']}/avatar.jpg"
        else:
            path = f"avatar-buyers/{user_id}/avatar.jpg"
        url = upload_image_base64(path, body.image_base64, body.content_type or "image/jpeg")
        # Fixed filename → cache-buster so the new avatar isn't served stale
        return {"success": True, "avatar_url": f"{url}?v={int(time.time())}"}
    except Exception as e:
        logger.exception(f"Exception in POST /users/me/avatar: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )


@router.get("/me/address")
def get_default_address(user=Depends(verify_token)):
    try:
        dao_addresses = DAOUserAddresses()
        address = dao_addresses.read_default_address(user["id"])
        return {"success": True, "address": address}
    except Exception as e:
        logger.exception(f"Exception in GET /users/me/address: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repr(e)}",
        )


@router.get("/info/{user_id}")
def get_user_profile(user_id: str, user=Depends(verify_token)):
    pass