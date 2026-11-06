from datetime import time
from typing import Optional

from pydantic import BaseModel
from typing_extensions import TypedDict  # pydantic needs this one on Python < 3.12


class DayHours(BaseModel):
    open: time
    close: time   # earlier than open = past midnight; equal = the whole day


# "1".."7" (1 = Monday), all required; null = day off. Plain field checks only: a custom validator's
# error would be a 500 (main.validation_exception_handler, see test_custom_validator_errors_should_be_422).
WeeklyHours = TypedDict("WeeklyHours", {str(d): Optional[DayHours] for d in range(1, 8)})


class RequestSetStoreHours(BaseModel):
    """null for the whole week = open all day (when the switch is on)."""
    weekly_hours: Optional[WeeklyHours]

    def as_json(self):
        if self.weekly_hours is None:
            return None
        return {d: h and {"open": h.open.strftime("%H:%M"), "close": h.close.strftime("%H:%M")}
                for d, h in self.weekly_hours.items()}
