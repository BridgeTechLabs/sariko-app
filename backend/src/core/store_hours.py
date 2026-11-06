import logging
from datetime import datetime, time, timedelta, timezone

logger = logging.getLogger(__name__)

# Vietnam has no DST, so a fixed offset is exact (and needs no tzdata in the image).
VN_TZ = timezone(timedelta(hours=7))


# ponytail: one slot per day (two slots, e.g. a lunch break, = a list per day later); weekly_hours has no DB check,
# only PATCH /sellers/me/hours validates it, so a malformed day here counts as a day off; open == close = the whole day.
def _open_since(weekly_hours: dict, now: datetime, seller_id=None):
    """Start of the opening-hours slot `now` falls in, or None if outside every slot.
    weekly_hours: {"1".."7" (1 = Monday): {"open": "HH:MM", "close": "HH:MM"} | None (day off)}.
    A slot belongs to the day it opens, so Friday 18:00-02:00 still covers 01:00 Saturday.
    Closing time is exclusive; open == close = the whole of that day."""
    local = now.astimezone(VN_TZ)
    for day in (local.date() - timedelta(days=1), local.date()):  # yesterday first: a continuing slot opened earlier
        try:
            hours = weekly_hours.get(str(day.isoweekday()))
            if not hours:
                continue
            opens, closes = time.fromisoformat(hours["open"]), time.fromisoformat(hours["close"])
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.error(f"[StoreHours] seller={seller_id} bad weekly_hours {weekly_hours!r}: day {day.isoweekday()} counted as a day off")
            continue
        if opens == closes:
            opens = closes = time(0)
        start = datetime.combine(day, opens, VN_TZ)
        end = datetime.combine(day + timedelta(days=closes <= opens), closes, VN_TZ)
        if start <= local < end:
            return start
    return None


def is_open_now(is_open, weekly_hours, now: datetime = None, seller_id=None) -> bool:
    """The manual switch is the master: off = closed. On = open inside today's hours
    (or the after-midnight part of yesterday's), or all day if no weekly hours are set."""
    if is_open is False:
        return False
    if weekly_hours is None:
        return True
    return _open_since(weekly_hours, now or datetime.now(VN_TZ), seller_id) is not None


def confirm_deadline(paid_at: datetime, weekly_hours, opened_at: datetime,
                     now: datetime, window: timedelta, seller_id=None) -> datetime:
    """When a paid order the seller hasn't accepted gets auto-cancelled. The window
    (admin_settings.order_confirm_minutes) runs from the latest of: payment, the start
    of the opening-hours slot open now (an order paid while closed waits for the store to open),
    and the seller's last switch-on.
    Only meaningful while the store is open now: a closed store never times out."""
    start = max(paid_at, opened_at or paid_at)
    since = _open_since(weekly_hours, now, seller_id) if weekly_hours is not None else None
    return max(start, since or start) + window


def with_open_now(seller: dict) -> dict:
    """Buyer-facing reads: `is_open` means "open right now" (switch + hours)."""
    if seller is not None:
        seller["is_open"] = is_open_now(seller.get("is_open"), seller.get("weekly_hours"), seller_id=seller.get("id"))
    return seller
