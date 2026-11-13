from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RequestUpdateCartItem(BaseModel):
    id: Optional[UUID] = None             # cart_items.id
    food_item_id: Optional[str] = None    # the old JS (before option groups): its row without options
    quantity: int = Field(gt=0)
    variant_id: Optional[str] = None
