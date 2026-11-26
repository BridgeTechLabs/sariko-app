import math
import re
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# The AI Studio post a buyer came from (docs/dev/20261123-studio-integration QĐ-1), same patterns as the orders CHECKs
REF_PATTERNS = {"ref_code": r"[A-Za-z0-9_-]{1,64}", "ref_source": r"[a-z0-9_]{1,32}", "ref_slug": r".{1,200}"}


class RequestCreateOrder(BaseModel):
    delivery_method: Literal["pickup", "delivery"]
    delivery_address: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lon: Optional[float] = None
    delivery_fee: Optional[float] = None
    quotation_id: Optional[str] = None
    note: Optional[str] = None
    delivery_appointment: Optional[datetime] = None
    # The chosen address's receiver (docs/dev/delivery-recipient R2); an app without them still orders.
    # Lalamove publishes no length limit: these match the address form, so an oversized note never reaches it
    receiver_name: Optional[str] = Field(default=None, max_length=100)
    receiver_phone: Optional[str] = Field(default=None, max_length=20)
    delivery_note: Optional[str] = Field(default=None, max_length=500)
    # Untyped on purpose: a bad value becomes None below, never a 422 (QA #2, #10)
    ref_code: Any = None
    ref_source: Any = None
    ref_slug: Any = None
    ref_at: Any = None   # ms since epoch: the buyer's last tap on the post link

    @field_validator("ref_code", "ref_source", "ref_slug", "ref_at", mode="before")
    @classmethod
    def drop_bad_ref(cls, value, info):
        """A ref that does not fit is dropped: it must never stop the order."""
        if info.field_name == "ref_at":
            ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        else:
            ok = isinstance(value, str) and re.fullmatch(REF_PATTERNS[info.field_name], value)
        return value if ok else None

    @model_validator(mode="after")
    def validate_delivery_fields(self):
        if self.delivery_method == "delivery":
            if not self.delivery_address or not self.delivery_address.strip():
                raise ValueError("delivery_address is required for delivery orders")
            if self.delivery_lat is None or self.delivery_lon is None:
                raise ValueError("delivery_lat and delivery_lon are required for delivery orders")
        return self
