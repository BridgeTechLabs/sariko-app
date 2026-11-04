"""Vietnam wall-clock time (GMT+7)."""
from datetime import datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))


def vn_today(now: datetime = None) -> str:
    """Today's date in Vietnam as yyyy-MM-dd."""
    return (now or datetime.now(VN_TZ)).astimezone(VN_TZ).strftime("%Y-%m-%d")
