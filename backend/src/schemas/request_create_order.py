from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, model_validator


class RequestCreateOrder(BaseModel):
    delivery_method: Literal["pickup", "delivery"]
    delivery_address: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lon: Optional[float] = None
    delivery_fee: Optional[float] = None
    quotation_id: Optional[str] = None
    note: Optional[str] = None
    delivery_appointment: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_delivery_fields(self):
        if self.delivery_method == "delivery":
            if not self.delivery_address or not self.delivery_address.strip():
                raise ValueError("delivery_address is required for delivery orders")
            if self.delivery_lat is None or self.delivery_lon is None:
                raise ValueError("delivery_lat and delivery_lon are required for delivery orders")
        return self
