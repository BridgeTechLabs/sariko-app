from typing import List
from pydantic import BaseModel, Field, model_validator

from schemas.request_review_item import RequestReviewItem


class RequestCreateReview(BaseModel):
    order_id: str
    overall_rating: int = Field(ge=1, le=5)
    items: List[RequestReviewItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_items(self):
        # The DB rejects this too (uniq_review_order_item), but a 422 naming the field
        # beats a 409 for what is really a malformed payload.
        food_item_ids = [item.food_item_id for item in self.items]
        if len(food_item_ids) != len(set(food_item_ids)):
            raise ValueError("items contains the same food_item_id twice")
        return self
