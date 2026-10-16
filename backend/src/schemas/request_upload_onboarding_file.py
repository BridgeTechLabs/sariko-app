from typing import Optional
from pydantic import BaseModel


class RequestUploadOnboardingFile(BaseModel):
    kind: str
    item_key: Optional[str] = None
    file_base64: str
    content_type: Optional[str] = None  # informational only: the type is read from the bytes
