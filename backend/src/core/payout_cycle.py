"""Seller payout cycle (docs/dev/payout-cycle §6): every payout_cycle_days days from
payout_cycle_start_date (YYYYMMDD, Vietnam date) is a payout day P, paying the orders done from
P - delay - cycle + 1 to P - delay. 99991231 (off), or a done day + delay before the start date:
paid one day at a time, on done day + delay. Same rule as the admin's GET /admin/payouts/next-period."""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

OFF = 99991231


def cycle_start(value: int) -> date | None:
    """payout_cycle_start_date as a date; None = cycle off (99991231 or not a real date)."""
    if value == OFF:
        return None
    try:
        return date(value // 10000, value // 100 % 100, value % 100)
    except (TypeError, ValueError):
        logger.error(f"[Settings] invalid payout_cycle_start_date={value!r}, cycle off")
        return None


def expected_payout_date(done_day: date, delay: int, cycle: int, start: date | None) -> date:
    """First payout day on or after done_day + delay."""
    day = done_day + timedelta(days=delay)
    if start is None or day < start:
        return day
    return start + timedelta(days=-(-(day - start).days // cycle) * cycle)
