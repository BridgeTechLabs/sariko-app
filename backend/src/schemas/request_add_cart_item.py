from typing import Optional
from pydantic import BaseModel, Field


class RequestAddCartItem(BaseModel):
    seller_id: str
    food_item_id: str
    quantity: int = Field(default=1, gt=0)
    variant_id: Optional[str] = None
