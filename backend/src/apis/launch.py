from fastapi import APIRouter

from core.launch import NO_DATE, launch_status
from dao.dao_admin_config import DAOAdminConfig

router = APIRouter()


@router.get("/launch")
def get_launch():
    """Public. Before admin_settings public_launch_date (Vietnam date) the app shows "coming soon" on buyer pages."""
    return {"success": True, **launch_status(DAOAdminConfig().get_positive_int("public_launch_date", NO_DATE))}
