from typing import Optional
from pydantic import BaseModel, Field


class RequestUpdateCategory(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
