from typing import Optional
from pydantic import BaseModel, Field


class RequestReviewItem(BaseModel):
    food_item_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=500)
