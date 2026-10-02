from typing import Optional
from pydantic import BaseModel


class RequestQuotation(BaseModel):
    seller_id: str
    delivery_lat: float
    delivery_lon: float
    delivery_address: str
