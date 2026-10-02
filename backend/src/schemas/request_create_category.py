from typing import Optional
from pydantic import BaseModel, Field


class RequestCreateCategory(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: Optional[int] = 0
