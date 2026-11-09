"""InvoiceStatus — the doc's "Status" enum, viiAPI appendix 3 (enum list)."""
from enum import StrEnum


class InvoiceStatus(StrEnum):
    NEW = "new"                 # Created
    RELEASED = "released"       # Issued
    SIGNED = "signed"           # Digitally signed
    SIGN_ERROR = "sign_error"   # Digital signing failed
    DELETED = "deleted"         # Deleted
    CANCELED = "canceled"       # Cancelled
