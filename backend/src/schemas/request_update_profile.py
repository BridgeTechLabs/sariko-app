from typing import Optional
from pydantic import BaseModel


class RequestUpdateProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = None
    avatar_url: Optional[str] = None
    address: Optional[str] = None
    address_details: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
