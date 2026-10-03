from typing import Optional
from pydantic import BaseModel, Field


class RequestCreateUserAddress(BaseModel):
    address: str = Field(min_length=1)
    receiver_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1)
    label: Optional[str] = None
    lat: float
    lon: float
    note: Optional[str] = None
    street_name: Optional[str] = None
    is_default: bool = False
