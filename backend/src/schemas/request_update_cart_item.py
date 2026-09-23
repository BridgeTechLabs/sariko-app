from pydantic import BaseModel, Field


class RequestUpdateCartItem(BaseModel):
    food_item_id: str
    quantity: int = Field(gt=0)
