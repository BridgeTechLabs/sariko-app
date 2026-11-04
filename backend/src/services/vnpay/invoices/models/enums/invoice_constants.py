"""Fixed values Sariko sends on its commission invoices (used by services/vnpay/invoices/invoice_builder.py)."""
from decimal import Decimal

PAYMENT_METHOD = "TM/CK"
CURRENCY_EXCHANGE_RATE = Decimal(1)
CREATED_BY = "Sariko System"  # the admin route has no per-person identity (shared X-Api-Key)
# /join nationality → buyerNationalityCode. "Other" is free text, so it gets no code.
NATIONALITY_CODES = {"Philippines": "PH", "Vietnam": "VN"}
