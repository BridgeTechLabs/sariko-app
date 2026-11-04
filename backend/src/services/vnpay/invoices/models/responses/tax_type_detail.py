"""TaxTypeDetail — one entry of InvoiceDetail.taxTypes."""
from ..base import Amount
from .detail_model import DetailModel


class TaxTypeDetail(DetailModel):
    tax: str
    amount: Amount                         # taxable amount
    tax_amount: Amount
