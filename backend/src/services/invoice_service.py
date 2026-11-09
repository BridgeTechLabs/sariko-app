"""
Sariko's commission e-invoice to a seller, one per paid order.

VNPAY first, Sariko second: request_id is built from the highest invoice_no + 1 (next_invoice_no),
VNPAY creates the invoice, and only then is the invoices row saved (status issued; the DB assigns
its own invoice_no). A rejection or a timeout saves nothing and is only logged with its request_id;
the next try sends the same request_id again. Once saved, its PDF is copied from VNPAY into the
private bucket (invoices.pdf_path).
"""
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from services.vnpay.invoices.invoice_builder import build_commission_invoice
from dao.dao_invoices import DAOInvoices
from dao.dao_onboarding import DAOOnboarding
from dao.dao_orders import DAOOrders
from services.invoice_validation import InvoiceValidationService
from services.vnpay.invoices import get_invoice_service
from utils.storage import upload_private

logger = logging.getLogger(__name__)

INVOICE_TYPE = "vat"
PDF_BUCKET = "sariko-private"


def request_id_for(invoice_no: int) -> str:
    """4 → SARIKO-00000000004."""
    return f"SARIKO-{invoice_no:011d}"


def create_invoice(order_id: str) -> dict:
    """Issue the VAT invoice for `order_id` and return the saved invoices row.

    Raises ValueError for an invalid order, buyer data (services/invoice_validation) or an order that
    already has an invoice; VnpayInvoiceError when VNPAY rejects it; requests.RequestException when
    VNPAY does not answer (it may still have created it: reconcile by the logged request_id).
    """
    tax_code = os.getenv("SARIKO_TAX_CODE")
    invoice_symbol = os.getenv("SARIKO_INVOICE_SYMBOL")
    currency_unit = os.getenv("VNPAY_CURRENCY_UNIT")
    if not tax_code or not invoice_symbol or not currency_unit:
        raise RuntimeError("SARIKO_TAX_CODE, SARIKO_INVOICE_SYMBOL and VNPAY_CURRENCY_UNIT must be set")

    validator = InvoiceValidationService()
    order = validator.validate_order(order_id, DAOOrders().read_order_for_invoice(order_id))
    seller_id = order["seller_id"]
    application = DAOOnboarding().get_seller_invoice_info(seller_id)
    validator.validate_buyer(seller_id, application)

    dao_invoices = DAOInvoices()
    if dao_invoices.read_invoice_by_order_id(order_id):
        raise ValueError(f"Order {order_id} already has an invoice")

    invoice_no = dao_invoices.next_invoice_no()
    request = build_commission_invoice(order, request_id_for(invoice_no), tax_code, invoice_symbol, currency_unit,
                                       application)
    try:
        result = get_invoice_service().create_vat_original(request)
    except Exception:
        logger.exception(f"[INVOICE] VNPAY create failed, order={order_id} request_id={request.invoice.request_id}")
        raise

    try:
        saved = dao_invoices.create_invoice({
            "order_id": order_id,
            "seller_id": seller_id,
            "request_id": request.invoice.request_id,
            "status": "issued",
            "tax_code": tax_code,
            "invoice_type": INVOICE_TYPE,
            "invoice_symbol": result.invoice_symbol or invoice_symbol,
            "invoice_number": str(result.invoice_number) if result.invoice_number is not None else None,
            "invoice_created_date": result.invoice_created_date,
            "lookup_code": result.lookup_code,
            "tax_authority_code": result.tax_authority_code,
            "trace_id": result.trace_id,
            "total_amount_after_tax": str(request.invoice.total_amount_after_tax),
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_data": {
                "request": request.model_dump(mode="json", by_alias=True, exclude_none=True),
                "response": result.model_dump(mode="json", by_alias=True),
            },
        })
    except Exception:
        # VNPAY holds an invoice we have no row for: it must be saved by hand from this log line.
        logger.exception(f"[INVOICE] VNPAY created but saving failed, order={order_id} "
                         f"request_id={request.invoice.request_id} invoice_number={result.invoice_number}")
        raise

    return store_invoice_pdf(saved)


def pdf_path_for(invoice: dict) -> str:
    """invoices/<seller_id>/SARIKO-00000000004.pdf inside PDF_BUCKET."""
    return f"invoices/{invoice['seller_id']}/{invoice['request_id']}.pdf"


def store_invoice_pdf(invoice: dict) -> dict:
    """Copy the issued invoice's PDF from VNPAY into PDF_BUCKET and save its path; return the row.

    Overwrites an earlier copy (a later download can replace the unsigned PDF with the signed one).
    Errors are only logged and the row comes back without pdf_path: the invoice itself is already issued.
    """
    try:
        pdf = get_invoice_service().get_invoice_pdf(
            invoice["tax_code"], str(invoice["invoice_created_date"])[:10], invoice["request_id"],
        )
        path = pdf_path_for(invoice)
        upload_private(PDF_BUCKET, path, pdf, "application/pdf", upsert=True)
        return DAOInvoices().update_pdf_path(invoice["id"], path) or {**invoice, "pdf_path": path}
    except Exception:
        logger.exception(f"[INVOICE] storing PDF failed, invoice={invoice.get('id')} "
                         f"request_id={invoice.get('request_id')}")
        return invoice


def create_invoice_for_done_order(order: dict) -> None:
    """Background task after an order moves to done: the invoice for that order.

    An order with no commission (0% tier) has nothing to invoice and is skipped. Errors are only logged:
    the order is already done.
    """
    if Decimal(str(order.get("commission_amount") or 0)) <= 0:
        return
    try:
        create_invoice(order["id"])
    except Exception:
        logger.exception(f"[INVOICE] auto-create failed for done order={order['id']}")


class InvoiceNotFoundError(LookupError):
    pass


def download_invoice_pdf(invoice_id: str) -> tuple[bytes, str]:
    """Fetch an issued invoice's PDF from VNPAY; return (pdf bytes, file name).

    Raises InvoiceNotFoundError, ValueError when the invoice is not issued yet, VnpayInvoiceError when VNPAY
    rejects the call, requests.RequestException when VNPAY does not answer.
    """
    invoice = DAOInvoices().read_invoice_by_id(invoice_id)
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice {invoice_id} not found")
    if invoice["status"] != "issued" or not invoice.get("invoice_created_date"):
        raise ValueError(f"Invoice {invoice_id} is not issued (status={invoice['status']})")

    pdf = get_invoice_service().get_invoice_pdf(
        invoice["tax_code"], invoice["invoice_created_date"][:10], invoice["request_id"],
    )
    return pdf, f"{invoice['request_id']}.pdf"
