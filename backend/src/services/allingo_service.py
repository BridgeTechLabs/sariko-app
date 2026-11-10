"""
AllinGo delivery service: a second delivery company next to Lalamove (docs/dev/20261109-allingo-delivery, T161).
AllinGo resells Grab Express, Lalamove and XanhSM through one API; we take the cheapest on-demand quote.

Usage:
    from services import allingo_service
    if allingo_service.enabled():
        quote = allingo_service.get_allingo_service().quote(pickup, dropoff)
"""
import logging
import os
import time
import uuid
from decimal import Decimal

import requests

from dao.dao_admin_config import DAOAdminConfig
from services.lalamove_service import QuotationResult

logger = logging.getLogger(__name__)

# Protocol constants, not business parameters: the box equals Lalamove's LESS_THAN_3_KG; the companies are
# AllinGo partner slugs (env, the test key only sees "simulator").
PACKAGE = {"weight": 3, "length": 30, "width": 30, "height": 20}
# The driver collects nothing: the trip is paid from our AllinGo wallet (AllinGo's default is cash).
NO_CASH = {"cod_amount": 0, "delivery_payment_method": "credit", "payee": "sender"}
LIVE_ORDER = {"draft", "queued", "on_going"}

# AllinGo delivery.status -> the Lalamove strings deliveries.status and the frontend already use.
# pickup_failed, deliver_failed and unknown values: no entry = keep the current status (still in progress).
STATUS = {
    **dict.fromkeys(("queued", "pending", "pending_schedule"), "ASSIGNING_DRIVER"),
    **dict.fromkeys(("courier_assigned", "courier_to_origin", "courier_at_origin"), "ON_GOING"),
    **dict.fromkeys(("picked_up", "in_transit", "courier_to_destination", "courier_arrived_destination",
                     "courier_waiting_at_destination"), "PICKED_UP"),
    "completed": "COMPLETED",
    **dict.fromkeys(("canceled", "failed", "return_active", "return_finished", "lost", "damaged"), "CANCELED"),
}

# A failure once the courier has the food (stored PICKED_UP): lost / damaged / sent back, not a trip to book again (T177 A22).
LOST_AFTER_PICKUP = {"failed", "return_active", "return_finished", "lost", "damaged"}

WALLET_EMPTY = "allingo_wallet_empty"


def enabled() -> bool:
    """admin_settings delivery_provider_allingo = 1 sends new trips to AllinGo. A read error is Lalamove."""
    try:
        return DAOAdminConfig().get_int_in_range("delivery_provider_allingo", 0, 0, 1) == 1
    except Exception as e:
        logger.error(f"[ALLINGO] switch read failed, using Lalamove: {e}")
        return False


class AllingoError(Exception):
    """A short code only: AllinGo's body (a 402 holds the company wallet balance) goes to the log, never out."""

    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code, self.status = code, status

    @property
    def retryable(self) -> bool:   # AllinGo errors page: retry network errors, 5xx, 408, 429 only
        return self.status is None or self.status >= 500 or self.status in (408, 429)


def address(line: str, lat, lon, name: str = None, phone: str = None, note: str = None) -> dict:
    """An AllinGo Address. Contacts are only needed to book (the quote takes none, sandbox 09/11)."""
    found = {"address_line": line, "location": {"lat": float(lat or 0), "lng": float(lon or 0)},
             "contact_name": name, "contact_phone": phone, "note": note}
    return {k: v for k, v in found.items() if v}


def trip_fields(order: dict) -> dict:
    """deliveries columns for an AllinGo Order (POST /orders response or a GET /orders item)."""
    delivery = order.get("delivery") or {}
    fee = (order.get("fee") or {}).get("total")   # sandbox 09/11: fee {cod, total}, VND
    return {
        "provider": "allingo",
        "trip_fee": int(Decimal(str(fee))) if fee is not None else None,   # T180 A12
        "allingo_order_id": order["id"],
        "lalamove_order_id": None,
        "share_link": delivery.get("track_link") or "",
        "status": STATUS.get(delivery.get("status"), "ASSIGNING_DRIVER"),
    }


class AllingoService:
    def __init__(self):
        self.app_id = os.getenv("ALLINGO_APP_ID", "")
        self.app_secret = os.getenv("ALLINGO_APP_SECRET", "")
        self.base_url = os.getenv("ALLINGO_BASE_URL", "https://pro.allingo.vn/api/v1").rstrip("/")
        self.partner_ids = [p.strip() for p in os.getenv("ALLINGO_PARTNER_IDS", "grab,lalamove,gsm").split(",") if p.strip()]
        if not self.app_id or not self.app_secret:
            raise RuntimeError("ALLINGO_APP_ID and ALLINGO_APP_SECRET must be set")
        self._token, self._token_until = None, 0.0

    def _access_token(self) -> str:
        if not self._token or time.time() > self._token_until - 300:   # renew with < 5 minutes left
            resp = self._send("POST", "/oauth/token", {"grant_type": "client_credentials",
                                                       "app_id": self.app_id, "app_secret": self.app_secret}, {})
            data = resp.json()
            self._token, self._token_until = data["access_token"], time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _send(self, method: str, path: str, body, headers: dict, params: dict = None):
        try:
            resp = requests.request(method, f"{self.base_url}{path}", json=body, params=params, headers=headers, timeout=15)
        except requests.RequestException as e:
            logger.error(f"[ALLINGO] {method} {path} network error: {e}")
            raise AllingoError("allingo_unavailable") from None
        logger.info(f"[ALLINGO] {method} {path} → {resp.status_code}")
        if resp.status_code == 401 and path != "/oauth/token":
            return resp   # the caller renews the token once
        if not resp.ok:
            logger.error(f"[ALLINGO] {method} {path} → {resp.status_code}: {resp.text}")
            raise AllingoError(WALLET_EMPTY if resp.status_code == 402 else "allingo_unavailable"
                               if resp.status_code >= 500 else "allingo_rejected", resp.status_code)
        return resp

    def _request(self, method: str, path: str, body=None, params: dict = None, idempotency_key: str = None) -> dict:
        for _ in range(2):   # a 401 (token revoked by a secret rotation): new token once, call once more
            headers = {"Authorization": f"Bearer {self._access_token()}"}
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            resp = self._send(method, path, body, headers, params)
            if resp.status_code != 401:
                return resp.json() if resp.text else {}
            self._token = None
        logger.error(f"[ALLINGO] {method} {path} → 401 after a new token")
        raise AllingoError("allingo_unauthorized", 401)

    def quote(self, pickup: dict, dropoff: dict) -> QuotationResult:
        """Cheapest available quote that shows the driver (tracking.driver_info). None usable -> AllingoError."""
        data = self._request("POST", "/inquiries", self.inquiry(pickup, dropoff))
        quotes = data.get("quotes")
        if isinstance(quotes, dict):   # the Quickstart shape; the API answered a list on 09/11
            quotes = quotes.get("data")
        quotes = [q for q in quotes or [] if q.get("available")]
        usable = [q for q in quotes if (q.get("tracking") or {}).get("driver_info")]
        if len(usable) < len(quotes):
            logger.warning(f"[ALLINGO] {len(quotes) - len(usable)} available quote(s) dropped: no driver info")
        if not usable:
            raise AllingoError("allingo_no_quote")
        best = min(usable, key=lambda q: Decimal(str(q["price"])))   # min keeps the first of equal prices
        return QuotationResult(quotation_id=best["service_id"], stop_id_0=None, stop_id_1=None,
                               total_fee=int(Decimal(str(best["price"]))), currency=best.get("currency", "VND"),
                               distance_km=0)

    def inquiry(self, pickup: dict, dropoff: dict) -> dict:
        return {"pickup": pickup, "dropoff": dropoff, "package": PACKAGE, **NO_CASH,
                "type": "on_demand", "filter_partner_ids": self.partner_ids}

    def find_live_order(self, order_id: str) -> dict | None:
        """A trip still running for this Sariko order (an earlier try that timed out may have made one): order
        draft / queued / on_going AND its delivery not ended (a failed / lost / damaged trip can stay on_going).
        A failed lookup counts as none. Answer shape checked with the test key 09/11: {data, has_more, next_cursor}."""
        try:
            data = self._request("GET", "/orders", params={"external_reference": order_id})
        except AllingoError as e:
            logger.warning(f"[ALLINGO] lookup of trips for order={order_id} failed ({e.code}): booking without it")
            return None
        if not isinstance(data.get("data"), list):
            logger.warning(f"[ALLINGO] lookup of trips for order={order_id}: unexpected answer keys {sorted(data)}")
            return None
        return next((o for o in data["data"] if o.get("status") in LIVE_ORDER
                     and STATUS.get((o.get("delivery") or {}).get("status")) not in ("COMPLETED", "CANCELED")), None)

    def place_order(self, quote: QuotationResult, pickup: dict, dropoff: dict, order_id: str) -> dict:
        """POST /orders paid from the wallet. A new Idempotency-Key per call: AllinGo replays a stored
        error for a reused key (Q12, sandbox 09/11)."""
        body = {**self.inquiry(pickup, dropoff), "service_id": quote.quotation_id, "estimated_price": quote.total_fee,
                "deliverable_payment_method": "prepaid", "external_reference": order_id}
        return self._request("POST", "/orders", body, idempotency_key=f"sariko-{order_id}-{uuid.uuid4().hex}")

    def wallet_balance(self) -> int:
        """GET /wallet delivery_credit in whole đồng (VND has no minor unit; the test key answered an int + "VND"
        on 10/11, T162). A missing / non-numeric balance or another currency is an error, never 0."""
        data = self._request("GET", "/wallet")
        try:
            if data["currency"] != "VND":
                raise ValueError(data["currency"])
            return int(Decimal(str(data["delivery_credit"])))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            logger.error(f"[ALLINGO] GET /wallet: unexpected answer {sorted(data) if isinstance(data, dict) else type(data)}")
            raise AllingoError("allingo_bad_answer") from None

    def cancel_order(self, allingo_order_id: str) -> bool:
        """POST /orders/{id}/cancel; cancelling twice is harmless, so every call has its own key.
        The answer has refunded_amount (docs) or refund + canceled_at null (sandbox, Q20): only the status matters."""
        try:
            self._request("POST", f"/orders/{allingo_order_id}/cancel", {"reason": "Cancelled by Sariko"},
                          idempotency_key=f"sariko-cancel-{uuid.uuid4().hex}")
            return True
        except AllingoError as e:
            logger.error(f"[ALLINGO] cancel_order {allingo_order_id} failed: {e.code}")
            return False


_service_instance: AllingoService | None = None


def get_allingo_service() -> AllingoService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AllingoService()
    return _service_instance


def reset_allingo_service():
    """Force re-instantiation on next call (used in tests)."""
    global _service_instance
    _service_instance = None
