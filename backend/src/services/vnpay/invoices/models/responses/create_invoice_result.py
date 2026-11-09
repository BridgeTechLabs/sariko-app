"""CreateInvoiceResult — data of every viiAPI create endpoint."""
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CreateInvoiceResult(BaseModel):
    """GeneralInvoiceInfo returned by every create endpoint."""
    # VNPAY sends invoiceType as an int (1) though the doc says string, so numbers are accepted for str fields.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, coerce_numbers_to_str=True)

    request_id: str
    invoice_number: Optional[int] = None   # empty until the invoice is released
    invoice_symbol: Optional[str] = None
    invoice_type: Optional[str] = None
    invoice_created_date: Optional[str] = None
    tax_authority_code: Optional[str] = None
    lookup_code: Optional[str] = None
    trace_id: Optional[str] = None         # from the envelope, kept for support tickets
