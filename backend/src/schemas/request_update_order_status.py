from typing import Literal, Optional
from pydantic import BaseModel, Field


class RequestUpdateOrderStatus(BaseModel):
    status: Literal["confirmed", "ready", "done", "cancelled"]
    cancellation_reason: Optional[str] = None   # a code from apis/sellers.SELLER_CANCEL_REASONS (T178)
    cancellation_note: Optional[str] = Field(default=None, max_length=300)   # the seller's own words for "other"
