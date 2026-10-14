from datetime import datetime, time, timedelta, timezone

# Vietnam has no DST, so a fixed offset is exact (and needs no tzdata in the image).
VN_TZ = timezone(timedelta(hours=7))


def is_open_now(is_open, opening_time, closing_time, now: datetime = None) -> bool:
    """The manual switch is the master: off = closed. On = open inside the daily hours,
    or all day if no hours are set. Hours may cross midnight (18:00–02:00).
    Times come from Postgres `time` columns as "HH:MM:SS" strings."""
    if is_open is False:
        return False
    if not opening_time or not closing_time:
        return True
    opens, closes = time.fromisoformat(opening_time), time.fromisoformat(closing_time)
    if opens == closes:
        return True
    t = (now or datetime.now(VN_TZ)).astimezone(VN_TZ).time()
    return opens <= t < closes if opens < closes else (t >= opens or t < closes)


def confirm_deadline(paid_at: datetime, opening_time, closing_time, opened_at: datetime,
                     now: datetime, window: timedelta) -> datetime:
    """When a paid order the seller hasn't accepted gets auto-cancelled. The window
    (admin_settings.order_confirm_minutes) runs from the latest of: payment, the start
    of today's opening hours (an order paid while closed waits for the store to open),
    and the seller's last switch-on.
    Only meaningful while the store is open now: a closed store never times out."""
    start = max(paid_at, opened_at or paid_at)
    if opening_time and closing_time and time.fromisoformat(opening_time) != time.fromisoformat(closing_time):
        local = now.astimezone(VN_TZ)
        opens = datetime.combine(local.date(), time.fromisoformat(opening_time), VN_TZ)
        if opens > local:  # hours cross midnight and it's after midnight: opened yesterday
            opens -= timedelta(days=1)
        start = max(start, opens)
    return start + window


def with_open_now(seller: dict) -> dict:
    """Buyer-facing reads: `is_open` means "open right now" (switch + hours)."""
    if seller is not None:
        seller["is_open"] = is_open_now(seller.get("is_open"), seller.get("opening_time"), seller.get("closing_time"))
    return seller
