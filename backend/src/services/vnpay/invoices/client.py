"""VNPAY Invoice endpoints. Order → payload mapping lives outside this package."""
import base64
import binascii
import re
from urllib.parse import quote

from .errors import VnpayInvoiceError
from .http import InvoiceHttp
from .models import CreateInvoiceResult, InvoiceDetail, OriginalVatInvoiceRequest


class VnpayInvoiceService:
    VAT_ORIGINAL_PATH = "/api/v6/vat/original"
    DETAIL_PATH = "/api/v6/invoices/{tax_code}/{request_id}"
    PDF_PATH = "/api/v6/invoices/pdf"

    def __init__(self, http: InvoiceHttp):
        self.http = http

    def create_vat_original(self, request: OriginalVatInvoiceRequest) -> CreateInvoiceResult:
        """Doc section 1.1: create an original VAT invoice. Raises VnpayInvoiceError on code != "00"."""
        data, trace_id = self.http.post(self.VAT_ORIGINAL_PATH, request.to_wire())
        # The doc types `data` as an array of GeneralInvoiceInfo, its examples show one object.
        if isinstance(data, list):
            data = data[0]
        return CreateInvoiceResult.model_validate({**data, "traceId": trace_id})

    def get_invoice(self, tax_code: str, request_id: str) -> InvoiceDetail:
        """Doc section 9: invoice detail. Raises VnpayInvoiceError on code != "00"."""
        path = self.DETAIL_PATH.format(tax_code=quote(tax_code, safe=""), request_id=quote(request_id, safe=""))
        data, trace_id = self.http.get(path, {})
        if not data:
            raise VnpayInvoiceError("00", "Invoice data is empty", trace_id)
        return InvoiceDetail.model_validate({**data, "traceId": trace_id})

    def get_invoice_pdf(self, tax_code: str, invoice_date: str, request_id: str) -> bytes:
        """Doc section 11: PDF of an invoice. `invoice_date` is its invoiceCreatedDate (yyyy-MM-dd)."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", invoice_date):
            raise ValueError(f"invoice_date must be yyyy-MM-dd, got {invoice_date!r}")
        data, trace_id = self.http.get(self.PDF_PATH, {
            "taxCode": tax_code, "invoiceDate": invoice_date, "requestId": request_id,
        })
        try:
            if not data:
                raise TypeError
            return base64.b64decode(data, validate=True)
        except (binascii.Error, TypeError):
            raise VnpayInvoiceError("00", "PDF data is empty or not base64", trace_id)
