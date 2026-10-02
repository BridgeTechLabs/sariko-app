from typing import Literal, Optional
from pydantic import BaseModel


class RequestUpdateOrderStatus(BaseModel):
    status: Literal["confirmed", "ready", "done", "cancelled"]
    cancellation_reason: Optional[str] = None
