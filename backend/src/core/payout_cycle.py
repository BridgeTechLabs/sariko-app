"""Seller payouts every week (docs/dev/payout-auto Q1-Q2): a period is payout_period_weeks whole weeks, Monday
00:00 to Sunday 23:59 Vietnam time (periods of several weeks follow each other from ANCHOR); it is paid on the
next payout_weekday (1 = Monday ... 7 = Sunday), made automatically at payout_generate_hour. An order goes in once
its complaint window is over when the payout is made, else into the next period. Same rule as the admin backend
(core/payout_cycle.py there) and the DB cut-off admin_payout_done_before()."""
from datetime import date, datetime, time, timedelta

from core.store_hours import VN_TZ

ANCHOR = date(2026, 10, 26)   # a Monday: only splits periods of more than 1 week


def period_end(day: date, weeks: int) -> date:
    """The Sunday ending the period that contains this Vietnam date."""
    length = 7 * weeks
    return ANCHOR + timedelta(days=(day - ANCHOR).days // length * length + length - 1)


def expected_payout_date(done_at: datetime, weeks: int, weekday: int, hour: int, window_hours: int) -> date:
    """Payout day of the first period whose payout is made after this order's complaint window ends."""
    end = period_end(done_at.astimezone(VN_TZ).date(), weeks)
    while True:
        payday = end + timedelta(days=weekday)
        if done_at + timedelta(hours=window_hours) <= datetime.combine(payday, time(hour), VN_TZ):
            return payday
        end += timedelta(days=7 * weeks)
