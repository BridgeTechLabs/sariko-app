from typing import Optional


class VnpayInvoiceError(Exception):
    """viiAPI answered with code != "00" (or a non-JSON error). Always carries traceId when VNPAY sent one."""

    def __init__(self, code: Optional[str], message: str, trace_id: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(f"[{code}] {message} (traceId={trace_id}, http={http_status})")
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.http_status = http_status
