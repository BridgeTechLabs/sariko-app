import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VnpayInvoiceConfig:
    base_url: str
    client_id: str
    client_secret: str
    timeout: int = 20

    @classmethod
    def from_env(cls) -> "VnpayInvoiceConfig":
        base_url      = os.getenv("VNPAY_INVOICE_URL", "").rstrip("/")
        client_id     = os.getenv("VNPAY_INVOICE_CLIENT_ID", "")
        client_secret = os.getenv("VNPAY_INVOICE_CLIENT_SECRET", "")
        if not base_url or not client_id or not client_secret:
            raise RuntimeError(
                "VNPAY_INVOICE_URL, VNPAY_INVOICE_CLIENT_ID and VNPAY_INVOICE_CLIENT_SECRET must be set"
            )
        return cls(base_url=base_url, client_id=client_id, client_secret=client_secret)
