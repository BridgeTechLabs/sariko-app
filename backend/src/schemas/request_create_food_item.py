from typing import Optional
from pydantic import BaseModel, Field


class RequestCreateFoodItem(BaseModel):
    category_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    price: float = Field(gt=0)
    unit_label: Optional[str] = None
    min_quantity: Optional[int] = Field(default=1, ge=1)
    quantity_step: Optional[int] = Field(default=1, ge=1)
    preorder_day: Optional[int] = Field(default=0, ge=0)
    is_available: Optional[bool] = True
    is_featured: Optional[bool] = False
    image_url: Optional[str] = None
