from typing import Optional
from pydantic import BaseModel


class RequestUploadImage(BaseModel):
    image_base64: str
    content_type: Optional[str] = None
