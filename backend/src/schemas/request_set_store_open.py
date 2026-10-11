from pydantic import BaseModel


class RequestSetStoreOpen(BaseModel):
    is_open: bool
