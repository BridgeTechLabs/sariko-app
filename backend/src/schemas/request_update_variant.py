from typing import Optional

from pydantic import BaseModel, Field


class RequestUpdateVariant(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[float] = Field(default=None, gt=0)
    sort_order: Optional[int] = None
    is_available: Optional[bool] = None
