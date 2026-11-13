from typing import Optional
from pydantic import BaseModel, Field


class RequestCreateFoodItem(BaseModel):
    category_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    price: int = Field(gt=0)
    unit_label: Optional[str] = None
    min_quantity: Optional[int] = Field(default=1, ge=1)
    quantity_step: Optional[int] = Field(default=1, ge=1)
    preorder_day: Optional[int] = Field(default=0, ge=0)
    is_available: Optional[bool] = True
    stock: Optional[int] = Field(default=None, ge=0, le=100000)   # portions left to sell; null = no limit (QĐ2-11)
    daily_portions: Optional[int] = None   # ignored: an app from before the stock (one release), then drop it
    is_featured: Optional[bool] = False
    image_url: Optional[str] = None
