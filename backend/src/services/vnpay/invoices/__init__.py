"""
VNPAY Invoice (viiAPI, e-invoice) client.

Usage:
    from services.vnpay.invoices import get_invoice_service, OriginalVatInvoiceRequest
    result = get_invoice_service().create_vat_original(OriginalVatInvoiceRequest(...))
"""
from .auth import TokenManager
from .client import VnpayInvoiceService
from .config import VnpayInvoiceConfig
from .errors import VnpayInvoiceError
from .http import InvoiceHttp
from .models import (
    CreateInvoiceResult,
    ExtraField,
    ExtraFieldDetail,
    Fee,
    InvoiceDetail,
    InvoiceStatus,
    OriginalVatInvoice,
    OriginalVatInvoiceRequest,
    ProductDetail,
    SignStatus,
    SpecialProduct,
    SpecialProductItem,
    TaxRateCode,
    TaxType,
    TaxTypeDetail,
    TvanStatus,
    VatProduct,
)

_token_manager: TokenManager | None = None
_invoice_service: VnpayInvoiceService | None = None


def get_token_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager(VnpayInvoiceConfig.from_env())
    return _token_manager


def get_invoice_service() -> VnpayInvoiceService:
    global _invoice_service
    if _invoice_service is None:
        _invoice_service = VnpayInvoiceService(InvoiceHttp(get_token_manager()))
    return _invoice_service


def reset_token_manager():
    """Force re-instantiation on next call (used in tests)."""
    global _token_manager, _invoice_service
    _token_manager = None
    _invoice_service = None
