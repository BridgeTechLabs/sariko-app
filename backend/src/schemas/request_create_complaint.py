from pydantic import BaseModel


class RequestCreateComplaint(BaseModel):
    order_id: str
    category: str
    description: str
