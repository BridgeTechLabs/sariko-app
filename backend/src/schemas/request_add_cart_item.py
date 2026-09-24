from typing import Optional
from pydantic import BaseModel


class RequestAddCartItem(BaseModel):
    seller_id: str
    food_item_id: str
    quantity: Optional[int] = 1
