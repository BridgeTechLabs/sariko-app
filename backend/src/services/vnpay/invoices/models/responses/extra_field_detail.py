"""ExtraFieldDetail — one entry of InvoiceDetail.extraFields."""
from typing import Optional

from .detail_model import DetailModel


class ExtraFieldDetail(DetailModel):
    code: str
    data: Optional[str] = None
