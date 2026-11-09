"""
VNPAY Invoice token — live check
================================
Manual script — hits the REAL viiAPI token endpoint. Not run by pytest.

Set VNPAY_INVOICE_URL / VNPAY_INVOICE_CLIENT_ID / VNPAY_INVOICE_CLIENT_SECRET
in backend/src/envs/.env.local, then from project root:
    python tests/manual/test_vnpay_invoice_token_live.py

Prints expiresIn so we can confirm its unit (auth.py assumes seconds).
"""
import logging
import os
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).parent.parent.parent / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from dotenv import load_dotenv
load_dotenv(BACKEND_SRC / "envs" / f".env.{os.environ.get('ENV', 'local')}")

logging.basicConfig(level=logging.INFO)

from services.vnpay.invoices import get_token_manager

tm = get_token_manager()
token = tm.get_token()
print(f"accessToken: {token[:12]}… (len={len(token)})")
print(f"cached until (monotonic): {tm._expires_at:.0f}, now: {tm._clock():.0f}")
assert tm.get_token() == token, "second call should hit the cache"
print("OK")
