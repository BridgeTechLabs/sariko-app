"""
Authorized viiAPI calls: Bearer token, {code, message, traceId, data} envelope, traceId logging.

No retry on timeout / 5xx: a create call may have gone through, and re-sending the same
requestId is not idempotent on VNPAY's side. Only a 401 is retried (once, with a new token),
since VNPAY rejected the request before processing it.
"""
import json
import logging
from decimal import Decimal

import requests

from .auth import TokenManager
from .errors import VnpayInvoiceError

logger = logging.getLogger(__name__)


def _json_default(value):
    # Amounts are Decimal in the models; viiAPI expects JSON numbers, not strings.
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class InvoiceHttp:
    def __init__(self, token_manager: TokenManager):
        self.tokens = token_manager
        self.config = token_manager.config

    def post(self, path: str, body: dict):
        """POST `body` to `path`; return the envelope's `data` and its traceId."""
        wire = json.dumps(body, default=_json_default, ensure_ascii=False).encode()
        return self._call("POST", path, lambda: self._send(path, wire))

    def get(self, path: str, params: dict):
        """GET `path` with query `params`; return the envelope's `data` and its traceId."""
        return self._call("GET", path, lambda: requests.get(
            f"{self.config.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.tokens.get_token()}"},
            timeout=self.config.timeout,
        ))

    def _call(self, method: str, path: str, send):
        resp = send()
        if resp.status_code == 401:
            self.tokens.invalidate()
            resp = send()

        try:
            payload = resp.json()
        except ValueError:
            logger.error(f"[VNPAY_INVOICE] {method} {path} → {resp.status_code}, non-JSON body: {resp.text[:200]}")
            raise VnpayInvoiceError(None, "Non-JSON response", http_status=resp.status_code)

        trace_id = payload.get("traceId")
        if payload.get("code") != "00":
            logger.error(f"[VNPAY_INVOICE] {method} {path} → {resp.status_code} code={payload.get('code')} message={payload.get('message')} traceId={trace_id}")
            raise VnpayInvoiceError(payload.get("code"), payload.get("message") or "Request failed", trace_id, resp.status_code)

        logger.info(f"[VNPAY_INVOICE] {method} {path} → {resp.status_code} traceId={trace_id}")
        return payload.get("data"), trace_id

    def _send(self, path: str, wire: bytes):
        return requests.post(
            f"{self.config.base_url}{path}",
            data=wire,
            headers={
                "Authorization": f"Bearer {self.tokens.get_token()}",
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
        )
