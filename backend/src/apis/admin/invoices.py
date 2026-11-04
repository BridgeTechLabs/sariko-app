import requests
from fastapi import APIRouter, HTTPException, status

from schemas.request_create_invoices import RequestCreateInvoices
from services.invoice_service import create_invoices
from services.vnpay.invoices import VnpayInvoiceError

router = APIRouter(prefix="/admin/invoices")


@router.post("")
def create_invoice(body: RequestCreateInvoices):
    try:
        invoice = create_invoices(body.order_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except VnpayInvoiceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"VNPAY rejected the invoice: [{e.code}] {e.message}")
    except requests.RequestException:
        # The invoice stays pending: VNPAY may have created it.
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                            detail="VNPAY did not answer, invoice left pending")

    return {"success": True, "invoice": invoice}
