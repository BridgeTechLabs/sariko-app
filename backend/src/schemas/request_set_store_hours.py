from datetime import time
from typing import Optional

from pydantic import BaseModel, model_validator


class RequestSetStoreHours(BaseModel):
    """Daily hours, same every day. Both null = open all day (when the switch is on)."""
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None

    @model_validator(mode="after")
    def both_or_neither(self):
        if (self.opening_time is None) != (self.closing_time is None):
            raise ValueError("Set both opening and closing time, or neither")
        return self
