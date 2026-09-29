from typing import Optional

from pydantic import BaseModel, Field


class RequestCreateVariant(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0)
    sort_order: Optional[int] = 0
    is_available: Optional[bool] = True
