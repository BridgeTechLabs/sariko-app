from fastapi import APIRouter, Depends

from core.auth import verify_admin_key
from apis.admin import invoices

# Every route under apis/admin/ requires X-Api-Key; add sub-routers here.
router = APIRouter(dependencies=[Depends(verify_admin_key)])
router.include_router(invoices.router)
