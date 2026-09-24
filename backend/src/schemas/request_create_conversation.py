from pydantic import BaseModel


class RequestCreateConversation(BaseModel):
    seller_slug: str
