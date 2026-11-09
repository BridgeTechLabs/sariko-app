"""VAT (GTGT) invoice models — OriginalVatInvoiceRequest and its parts (viiAPI appendix 1)."""
from typing import Annotated, Optional

from pydantic import Field

from .base import Amount, CamelModel, IsoDate, TaxRate


class SpecialProductItem(CamelModel):
    special_product_code: str              # e.g. TNGHang, DCNGHang, MSTNGHang, MDDNGHang
    special_product_value: str


class SpecialProduct(CamelModel):
    special_product_type: int              # 1 car/motorbike, 2 transport, 3 transport via digital/e-commerce platform
    special_product_items: list[SpecialProductItem]


class VatProduct(CamelModel):
    ordinal_number: int
    name: Annotated[str, Field(max_length=500)]
    property: int                          # 1 goods/service, 2 promotion, 3 trade discount, 4 note
    amount_without_discount: Amount
    amount: Amount                         # before tax, after discount
    tax: TaxRate
    tax_amount: Amount
    amount_after_tax: Amount
    code: Optional[Annotated[str, Field(max_length=50)]] = None
    unit: Optional[Annotated[str, Field(max_length=50)]] = None
    quantity: Optional[Amount] = None
    price: Optional[Amount] = None
    discount_rate: Optional[Amount] = None
    discount_amount: Optional[Amount] = None
    special_product: Optional[SpecialProduct] = None


class TaxType(CamelModel):
    """One entry per tax rate used in products — no extra, no missing."""
    tax: TaxRate
    amount: Amount                         # taxable amount
    tax_amount: Amount


class Fee(CamelModel):
    fee_code: str                          # must exist in the fee catalogue on VNPAY Invoice
    fee_amount: Amount


class ExtraField(CamelModel):
    code: str                              # must be registered on VNPAY Invoice first
    data: Annotated[str, Field(max_length=500)]


def _str(n: int):
    return Optional[Annotated[str, Field(max_length=n)]]


class OriginalVatInvoice(CamelModel):
    request_id: str                        # unique across the whole VNPAY system
    invoice_created_date: IsoDate
    invoice_symbol: Annotated[str, Field(max_length=6)]
    payment_method: str                    # e.g. "TM/CK"
    currency_unit: str = "VND"
    total_amount_without_discount: Amount
    total_amount: Amount                   # before tax, after discount
    total_tax_amount: Amount
    total_amount_after_tax: Amount
    products: list[VatProduct]
    tax_types: list[TaxType]

    currency_exchange_rate: Optional[Amount] = None
    discount: Optional[bool] = None
    total_discount_amount: Optional[Amount] = None   # required by VNPAY when discount=True
    total_fee_amount: Optional[Amount] = None
    total_payment_in_word: _str(255) = None
    receipt: _str(50) = None
    buyer_customer_code: _str(50) = None
    buyer_tax_code: _str(14) = None
    buyer_name: _str(100) = None
    buyer_address: _str(400) = None
    buyer_full_name: _str(400) = None      # buyer's organization name
    buyer_phone_number: _str(20) = None
    buyer_email: _str(50) = None
    buyer_bank_name: _str(400) = None
    buyer_bank_account_number: _str(30) = None
    buyer_passport_number: _str(20) = None
    buyer_id_number: _str(12) = None
    buyer_budget_relation_unit_code: _str(7) = None
    buyer_fax: _str(20) = None
    buyer_province_code: _str(2) = None
    buyer_commune_code: _str(5) = None
    buyer_foreign_organization_id: _str(50) = None
    buyer_nationality_code: _str(2) = None
    buyer_nationality: _str(50) = None
    invoice_note: _str(255) = None
    internal_note: _str(255) = None
    branch_code: _str(50) = None
    is_petrol_invoice: Optional[bool] = None
    financial_leasing_invoice: Optional[bool] = None  # invoice for a financial leasing activity
    is_seller_gasoline_business: Optional[bool] = None  # seller trades in petrol; VNPAY default false
    is_asset_ownership_registration: Optional[bool] = None  # invoice form for registering asset ownership (cars...)
    # Asset auction by an assigned authority; VNPAY default false. When true, auctionAuthorityName /
    # Address / TaxCode become required (not modelled yet).
    has_auction_authority_info: Optional[bool] = None
    is_send_mail: Optional[bool] = None
    auto_calculate_product: Optional[bool] = None
    extra_fields: Optional[list[ExtraField]] = None
    fees: Optional[list[Fee]] = None
    created_by: _str(255) = None
    lookup_code: _str(50) = None
    seller_store_code: _str(50) = None
    seller_store_name: _str(400) = None


class OriginalVatInvoiceRequest(CamelModel):
    tax_code: str                          # seller's tax code (MST)
    invoice: OriginalVatInvoice
    # None = not sent; VNPAY's own config wins over these anyway.
    auto_release: Optional[bool] = None
    auto_sign: Optional[bool] = None
    auto_send_cqt: Optional[bool] = Field(default=None, alias="autoSendCQT")
