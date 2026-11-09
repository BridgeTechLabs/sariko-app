"""InvoiceDetail — data of GET /api/v6/invoices/{taxCode}/{requestId}."""
from typing import Optional

from ..base import Amount
from ..enums import InvoiceStatus, SignStatus, TvanStatus
from .detail_model import DetailModel
from .extra_field_detail import ExtraFieldDetail
from .product_detail import ProductDetail
from .tax_type_detail import TaxTypeDetail


class InvoiceDetail(DetailModel):
    """GET /api/v6/invoices/{taxCode}/{requestId} — doc section 9, model InvoiceDetail."""
    request_id: str
    seller_tax_code: Optional[str] = None
    seller_name: Optional[str] = None
    invoice_created_date: Optional[str] = None   # yyyy-MM-dd
    invoice_type: Optional[str] = None           # InvoiceType: "1" VAT, "2" sale, ...
    invoice_symbol: Optional[str] = None
    invoice_number: Optional[int] = None
    ref_request_id: Optional[str] = None
    related_invoice_created_date: Optional[str] = None
    related_invoice_type: Optional[str] = None
    related_invoice_symbol: Optional[str] = None
    related_invoice_number: Optional[int] = None
    payment_method: Optional[str] = None
    currency_unit: Optional[str] = None
    currency_exchange_rate: Optional[Amount] = None
    receipt: Optional[str] = None
    lookup_code: Optional[str] = None
    tax_authority_code: Optional[str] = None
    buyer_customer_code: Optional[str] = None
    buyer_tax_code: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_full_name: Optional[str] = None        # buyer's organization name
    buyer_phone_number: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_bank_name: Optional[str] = None
    buyer_bank_account_number: Optional[str] = None
    warehouse_address: Optional[str] = None
    seller_internal_dispatch_command: Optional[str] = None
    seller_consignee_name: Optional[str] = None
    seller_contract_no: Optional[str] = None
    seller_contract_day: Optional[str] = None
    seller_transportation: Optional[str] = None
    seller_transformer_name: Optional[str] = None
    invoice_note: Optional[str] = None
    discount: Optional[bool] = None
    total_amount_without_discount: Optional[Amount] = None
    total_discount_amount: Optional[Amount] = None
    total_amount: Optional[Amount] = None        # before tax, after discount
    total_tax_amount: Optional[Amount] = None
    total_amount_after_tax: Optional[Amount] = None
    total_payment_in_word: Optional[str] = None
    branch_code: Optional[str] = None
    source: Optional[str] = None
    status: Optional[InvoiceStatus] = None       # the doc's "Status" enum
    invoice_status: Optional[str] = None         # InvoiceStatus: origin/adjustment/adjusted/replacement/replaced/cancel
    tvan_status: Optional[TvanStatus] = None     # None means NOT_SENT too (per the doc)
    products: Optional[list[ProductDetail]] = None
    tax_types: Optional[list[TaxTypeDetail]] = None
    extra_fields: Optional[list[ExtraFieldDetail]] = None
    # Not in the doc, returned by the sandbox.
    id: Optional[int] = None
    sign_status: Optional[SignStatus] = None     # enum is in the doc's appendix, the field is not in InvoiceDetail
    buyer_fax: Optional[str] = None
    buyer_id_number: Optional[str] = None
    buyer_passport_number: Optional[str] = None
    buyer_budget_relation_unit_code: Optional[str] = None
    buyer_consignee_name: Optional[str] = None
    seller_digital_economic_contract: Optional[str] = None
    seller_economic_contract_day: Optional[str] = None
    seller_store_code: Optional[str] = None
    seller_store_name: Optional[str] = None
    financial_leasing_invoice: Optional[bool] = None
    trace_id: Optional[str] = None               # from the envelope, kept for support tickets
