from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RequestAddCartItem(BaseModel):
    seller_id: str
    food_item_id: str
    quantity: int = Field(default=1, gt=0)
    variant_id: Optional[str] = None
    option_ids: List[UUID] = Field(default_factory=list, max_length=30)   # input check (BM6), not a business cap
