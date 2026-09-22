from typing import Optional
from pydantic import BaseModel


class RequestReadCartItems(BaseModel):
    cart_id: Optional[str] = None
    seller_id: Optional[str] = None
