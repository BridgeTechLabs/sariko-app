"""TvanStatus — status of sending the invoice to the tax authority (CQT), viiAPI appendix 3 (enum list)."""
from enum import IntEnum


class TvanStatus(IntEnum):
    NOT_SENT = 1            # Not sent to the tax authority yet (VNPAY may also send null for this)
    AWAITING_RESPONSE = 2   # Waiting for the tax authority's response
    TVAN_ERROR = 3          # Sending through TVAN failed
    NOT_RECEIVED = 4        # Tax authority did not receive it
    ACCEPTED = 5            # Tax authority accepted
    REJECTED = 6            # Tax authority rejected
    RECEIVED = 7            # Tax authority received
    RESULT_RETURNED = 8     # Tax authority returned a result
    VALID = 9               # Tax authority returned: message valid
    INVALID = 10            # Tax authority returned: message invalid
