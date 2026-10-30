from typing import Optional
from pydantic import BaseModel, Field


class RequestCreateUserAddress(BaseModel):
    address: str = Field(min_length=1)
    receiver_name: str = Field(min_length=1, max_length=100)
    phone_number: str = Field(min_length=1, max_length=20)
    label: Optional[str] = None
    lat: float
    lon: float
    # street_name + " · " + note goes on the order as delivery_note (<= 500, delivery-recipient)
    note: Optional[str] = Field(default=None, max_length=250)
    street_name: Optional[str] = Field(default=None, max_length=200)
    is_default: bool = False
