from typing import Optional
from pydantic import BaseModel, Field


class RequestUpdateFoodItem(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    unit_label: Optional[str] = None
    min_quantity: Optional[int] = Field(default=None, ge=1)
    quantity_step: Optional[int] = Field(default=None, ge=1)
    preorder_day: Optional[int] = Field(default=None, ge=0)
    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None
    image_url: Optional[str] = None
