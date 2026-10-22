from fastapi import APIRouter

from core.launch import NO_DATE, launch_status
from dao.dao_admin_config import DAOAdminConfig

router = APIRouter()


@router.get("/launch")
def get_launch():
    """Public. Until admin_settings app_live = 1 the app shows "coming soon" on buyer pages."""
    config = DAOAdminConfig()
    return {"success": True, **launch_status(config.get_int_in_range("app_live", 0, 0, 1),
                                             config.get_positive_int("launch_date", NO_DATE))}
