from typing import Annotated, Optional
from pydantic import BaseModel, StringConstraints


class RequestUpdateProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = None
    avatar_url: Optional[str] = None
    address: Optional[str] = None
    address_details: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    # Sellers only (ignored for buyers). Display name only, the slug never changes, so shared links keep working.
    store_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]] = None
