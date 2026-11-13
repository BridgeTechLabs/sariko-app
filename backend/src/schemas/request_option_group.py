from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

# Input format (QĐ3-10), not a business cap: counted in characters, so Vietnamese marks and emoji are fine.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class RequestOption(BaseModel):
    id: Optional[UUID] = None    # an existing option of the group; none = a new one
    name: Name
    extra_price: int = Field(default=0, ge=0)   # whole đồng; 0 = free. The cap is admin_settings menu_option_max_extra_price
    is_available: bool = True


class RequestOptionGroup(BaseModel):
    """The whole group: saving it makes its options exactly this list, in this order."""
    name: Name
    is_required: bool = False
    max_select: int = Field(default=1, ge=1)
    options: List[RequestOption] = Field(min_length=1)


class RequestDishGroupOrder(BaseModel):
    group_ids: List[UUID]
