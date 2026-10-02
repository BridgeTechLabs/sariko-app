from pydantic import BaseModel


class RequestSetPinned(BaseModel):
    pinned: bool
