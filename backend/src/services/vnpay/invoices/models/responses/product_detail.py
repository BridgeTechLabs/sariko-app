"""ProductDetail — one line of InvoiceDetail.products."""
from typing import Optional

from ..base import Amount
from .detail_model import DetailModel


class ProductDetail(DetailModel):
    ordinal_number: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    property: Optional[int] = None         # 1 goods/service, 2 promotion, 3 trade discount, 4 note, 5 special goods
    unit: Optional[str] = None
    quantity: Optional[Amount] = None
    price: Optional[Amount] = None
    discount_rate: Optional[Amount] = None
    discount_amount: Optional[Amount] = None
    amount_without_discount: Optional[Amount] = None
    amount: Optional[Amount] = None        # before tax, after discount
    tax: Optional[str] = None
    tax_amount: Optional[Amount] = None
    amount_after_tax: Optional[Amount] = None
    # Not in the doc, returned by the sandbox.
    imported_quantity: Optional[Amount] = None
    note: Optional[str] = None
    special_product: Optional[dict] = None
