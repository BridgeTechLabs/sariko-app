from typing import Optional
from pydantic import BaseModel, Field


class RequestQuotation(BaseModel):
    seller_id: str
    delivery_lat: float
    delivery_lon: float
    delivery_address: str
    # The cart's chosen address (T191 S2): AllinGo's quote needs the receiver's contact, else the buyer's profile
    receiver_name: Optional[str] = Field(default=None, max_length=100)
    receiver_phone: Optional[str] = Field(default=None, max_length=20)
