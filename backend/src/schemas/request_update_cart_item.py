from uuid import UUID

from pydantic import BaseModel, Field


class RequestUpdateCartItem(BaseModel):
    id: UUID                              # cart_items.id
    quantity: int = Field(gt=0)
