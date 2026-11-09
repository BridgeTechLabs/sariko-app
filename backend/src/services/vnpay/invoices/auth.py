"""
viiAPI access token — POST /user/client/token {clientId, clientSecret}.

The token is cached in memory and fetched again shortly before it expires.
No refresh token exists: renewing = calling the token endpoint again.
"""
import logging
import threading
import time

import requests

from .config import VnpayInvoiceConfig
from .errors import VnpayInvoiceError

logger = logging.getLogger(__name__)


class TokenManager:
    TOKEN_PATH = "/user/client/token"
    REFRESH_MARGIN = 60  # seconds before expiry to fetch a new token

    def __init__(self, config: VnpayInvoiceConfig, clock=time.monotonic):
        self.config = config
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0
        # Sync routes run in FastAPI's threadpool — stop several threads fetching at once.
        self._lock = threading.Lock()

    def get_token(self) -> str:
        if self._is_valid():
            return self._token
        with self._lock:
            if not self._is_valid():
                self._fetch()
        return self._token

    def invalidate(self):
        """Drop the cached token (e.g. after a 401) so the next get_token() fetches a new one."""
        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def _is_valid(self) -> bool:
        return self._token is not None and self._clock() < self._expires_at

    def _fetch(self):
        url = f"{self.config.base_url}{self.TOKEN_PATH}"
        resp = requests.post(
            url,
            json={"clientId": self.config.client_id, "clientSecret": self.config.client_secret},
            timeout=self.config.timeout,
        )
        try:
            body = resp.json()
        except ValueError:
            logger.error(f"[VNPAY_INVOICE] token → {resp.status_code}, non-JSON body: {resp.text[:200]}")
            raise VnpayInvoiceError(None, "Non-JSON response from token endpoint", http_status=resp.status_code)

        trace_id = body.get("traceId")
        data = body.get("data") or {}
        if body.get("code") != "00" or not data.get("accessToken"):
            logger.error(f"[VNPAY_INVOICE] token → {resp.status_code} code={body.get('code')} message={body.get('message')} traceId={trace_id}")
            raise VnpayInvoiceError(body.get("code"), body.get("message") or "Token request failed", trace_id, resp.status_code)

        # expiresIn is in seconds (not stated in the doc; sandbox returns 21600 = JWT exp - iat).
        expires_in = float(data.get("expiresIn") or 0)
        self._token = data["accessToken"]
        self._expires_at = self._clock() + max(expires_in - self.REFRESH_MARGIN, expires_in / 2)
        logger.info(f"[VNPAY_INVOICE] token → {resp.status_code} expiresIn={data.get('expiresIn')} traceId={trace_id}")
