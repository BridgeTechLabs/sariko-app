"""SignStatus — viiAPI appendix 3 (enum list)."""
from enum import IntEnum


class SignStatus(IntEnum):
    INITIALIZED = 0   # Created
    PENDING = 1       # Waiting to be signed
    SIGNED = 2        # Digitally signed
    SIGN_ERROR = 3    # Digital signing failed
