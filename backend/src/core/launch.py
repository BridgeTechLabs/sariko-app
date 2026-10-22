"""Pre-launch switch: admin_settings public_launch_date (YYYYMMDD, Vietnam date)."""
from datetime import datetime

from core.store_hours import VN_TZ

NO_DATE = 99991231  # "coming soon", no opening date announced yet


def launch_status(launch_date: int, now: datetime | None = None) -> dict:
    """prelaunch while today in Vietnam is before launch_date; the date as YYYY-MM-DD, None for NO_DATE."""
    today = int((now or datetime.now(VN_TZ)).astimezone(VN_TZ).strftime("%Y%m%d"))
    shown = None if launch_date == NO_DATE else f"{launch_date // 10000:04d}-{launch_date // 100 % 100:02d}-{launch_date % 100:02d}"
    return {"prelaunch": today < launch_date, "launch_date": shown}
