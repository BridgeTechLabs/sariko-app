"""
Sariko's commission e-invoice to a seller, covering several of that seller's paid orders.

All or nothing: one invalid order stops the whole invoice before anything is written.
The invoice row and its invoice_orders are saved before calling VNPAY, so an order can never
end up in two active invoices (idx_invoice_orders_active_order_id).

Status: initial (saved on our side, not sent yet) → pending (being sent to VNPAY; stays pending
when the call times out and the outcome is unknown) → issued | failed.
"""
import logging
import os
from datetime import datetime, timezone

import requests
from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from services.vnpay.invoices.invoice_builder import build_commission_invoice
from dao.dao_invoices import DAOInvoices
from dao.dao_onboarding import DAOOnboarding
from dao.dao_orders import DAOOrders
from services.invoice_validation import InvoiceValidationService
from services.vnpay.invoices import VnpayInvoiceError, get_invoice_service

logger = logging.getLogger(__name__)

INVOICE_TYPE = "vat"


def create_invoices(order_ids: list[str]) -> dict:
    """Issue one VAT invoice for `order_ids` and return the saved invoices row.

    Raises ValueError for invalid orders or buyer data (services/invoice_validation), VnpayInvoiceError when VNPAY rejects the invoice,
    requests.RequestException when the outcome is unknown (the invoice stays pending).
    """
    order_ids = list(dict.fromkeys(order_ids))
    if not order_ids:
        raise ValueError("order_ids is empty")

    tax_code = os.getenv("SARIKO_TAX_CODE")
    invoice_symbol = os.getenv("SARIKO_INVOICE_SYMBOL")
    currency_unit = os.getenv("VNPAY_CURRENCY_UNIT")
    if not tax_code or not invoice_symbol or not currency_unit:
        raise RuntimeError("SARIKO_TAX_CODE, SARIKO_INVOICE_SYMBOL and VNPAY_CURRENCY_UNIT must be set")

    validator = InvoiceValidationService()
    orders = validator.validate_orders(order_ids, DAOOrders().read_orders_for_invoice(order_ids))
    seller_id = orders[0]["seller_id"]
    application = DAOOnboarding().get_seller_invoice_info(seller_id)
    validator.validate_buyer(seller_id, application)

    dao_invoices = DAOInvoices()
    # request_id (SARIKO-<invoice_no>) is filled by the DB on insert.
    invoice = dao_invoices.create_invoice({
        "seller_id": seller_id,
        "status": "initial",
        "tax_code": tax_code,
        "invoice_type": INVOICE_TYPE,
        "invoice_symbol": invoice_symbol,
    })

    request = build_commission_invoice(orders, invoice["request_id"], tax_code, invoice_symbol, currency_unit,
                                       application)
    request_snapshot = request.model_dump(mode="json", by_alias=True, exclude_none=True)
    dao_invoices.update_invoice(invoice["id"], {
        "total_amount_after_tax": str(request.invoice.total_amount_after_tax),
        "snapshot_data": {"request": request_snapshot},
    })

    try:
        dao_invoices.create_invoice_orders(invoice["id"], order_ids)
    except PostgrestExceptionAPIError as e:
        dao_invoices.update_invoice(invoice["id"], {"status": "failed", "error_message": str(e)[:500]})
        raise ValueError(f"Some orders already have an active invoice: {e}")

    dao_invoices.update_invoice(invoice["id"], {"status": "pending"})
    try:
        result = get_invoice_service().create_vat_original(request)
    except VnpayInvoiceError as e:
        dao_invoices.update_invoice(invoice["id"], {
            "status": "failed", "error_code": e.code, "error_message": e.message, "trace_id": e.trace_id,
        })
        dao_invoices.deactivate_invoice_orders(invoice["id"])
        raise
    except requests.RequestException:
        # VNPAY may have created it: keep pending + orders locked until reconciled by request_id.
        logger.exception(f"[INVOICE] create outcome unknown, request_id={request.invoice.request_id}")
        raise

    return dao_invoices.update_invoice(invoice["id"], {
        "status": "issued",
        "invoice_number": str(result.invoice_number) if result.invoice_number is not None else None,
        "invoice_symbol": result.invoice_symbol or invoice_symbol,
        "invoice_created_date": result.invoice_created_date,
        "lookup_code": result.lookup_code,
        "tax_authority_code": result.tax_authority_code,
        "trace_id": result.trace_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_data": {"request": request_snapshot, "response": result.model_dump(mode="json", by_alias=True)},
    })
