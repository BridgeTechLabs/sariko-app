"""
Lalamove delivery service — Lalamove v3 API with HMAC auth.

Usage:
    from services.lalamove_service import get_lalamove_service
    service = get_lalamove_service()
    quote = service.get_quotation(...)
"""
import json
import os
import time
import hmac
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class QuotationResult(BaseModel):
    quotation_id: str
    stop_id_0: str          # stopId of pickup stop (from quotation response)
    stop_id_1: str          # stopId of dropoff stop (from quotation response)
    total_fee: int          # VND integer (e.g. 25000)
    currency: str           # "VND"
    distance_km: float      # e.g. 3.2

class PlaceOrderResult(BaseModel):
    lalamove_order_id: str
    status: str             # "ASSIGNING_DRIVER"
    share_link: str

class OrderStatusResult(BaseModel):
    status: str             # ASSIGNING_DRIVER | ON_GOING | PICKED_UP | COMPLETED | CANCELLED
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_plate: Optional[str] = None
    tracking_url: Optional[str] = None
    share_link: Optional[str] = None

# ---------------------------------------------------------------------------
# Lalamove v3 API client
# ---------------------------------------------------------------------------

class LalamoveService:
    """
    Lalamove v3 API client.
    Requires LALAMOVE_API_KEY, LALAMOVE_API_SECRET, LALAMOVE_BASE_URL env vars.
    Auth: HMAC-SHA256  →  Authorization: hmac {key}:{timestamp}:{signature}
    """

    def __init__(self):
        self.api_key    = os.getenv("LALAMOVE_API_KEY", "")
        self.api_secret = os.getenv("LALAMOVE_API_SECRET", "")
        self.base_url   = os.getenv("LALAMOVE_BASE_URL", "https://rest.lalamove.com").rstrip("/")
        self.market     = os.getenv("LALAMOVE_MARKET", "VN")
        if not self.api_key or not self.api_secret:
            raise RuntimeError("LALAMOVE_API_KEY and LALAMOVE_API_SECRET must be set")

    def _sign(self, method: str, path: str, body: str) -> tuple[str, str]:
        timestamp = str(int(time.time() * 1000))
        raw = f"{timestamp}\r\n{method.upper()}\r\n{path}\r\n\r\n{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()
        return timestamp, signature

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp, signature = self._sign(method, path, body)
        return {
            "Authorization": f"hmac {self.api_key}:{timestamp}:{signature}",
            "Market": self.market,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: dict | None = None):
        m = method.upper()
        if m in ("POST", "PATCH"):
            # v3: POST/PATCH bodies wrapped in {"data": {...}}
            wire = json.dumps({"data": body}) if body is not None else ""
        elif m == "DELETE":
            # DELETE signs/sends raw {} (no data envelope)
            wire = json.dumps(body) if body is not None else "{}"
        else:
            # GET: no body
            wire = ""

        headers = self._headers(method, path, wire)
        url = f"{self.base_url}{path}"
        resp = requests.request(
            method, url,
            headers=headers,
            data=wire.encode() if wire else None,
            timeout=15,
        )
        logger.info(f"[LALAMOVE] {method} {path} → {resp.status_code}")
        if not resp.ok:
            logger.error(f"[LALAMOVE] error: {resp.text}")
            resp.raise_for_status()
        if not resp.text:
            return {}
        payload = resp.json()
        return payload.get("data", payload)

    # ------------------------------------------------------------------

    def get_quotation(
        self,
        pickup_lat: float, pickup_lon: float, pickup_address: str,
        dropoff_lat: float, dropoff_lon: float, dropoff_address: str,
    ) -> QuotationResult:
        body = {
            "serviceType": "MOTORCYCLE",
            "language": "vi_VN",
            "stops": [
                {
                    "coordinates": {"lat": str(pickup_lat), "lng": str(pickup_lon)},
                    "address": pickup_address,
                },
                {
                    "coordinates": {"lat": str(dropoff_lat), "lng": str(dropoff_lon)},
                    "address": dropoff_address,
                },
            ],
            "item": {
                "quantity": "1",
                "weight": "LESS_THAN_3_KG",
                "categories": ["FOOD_DELIVERY"],
                "handlingInstructions": ["KEEP_UPRIGHT"],
            },
        }
        data = self._request("POST", "/v3/quotations", body)
        breakdown = data.get("priceBreakdown", {})
        distance  = data.get("distance", {})
        return QuotationResult(
            quotation_id=data["quotationId"],
            stop_id_0=data["stops"][0]["stopId"],
            stop_id_1=data["stops"][1]["stopId"],
            total_fee=int(Decimal(str(breakdown.get("total", 0)))),
            currency=breakdown.get("currency", "VND"),
            distance_km=float(distance.get("value", 0)),
        )

    def place_order(
        self,
        quotation_id: str,
        stop_id_0: str,
        stop_id_1: str,
        sender_name: str,
        sender_phone: str,
        recipient_name: str,
        recipient_phone: str,
        recipient_remarks: str = "",
    ) -> PlaceOrderResult:
        body = {
            "quotationId": quotation_id,
            "sender": {
                "stopId": stop_id_0,
                "name": sender_name,
                "phone": sender_phone,
            },
            "recipients": [
                {
                    "stopId": stop_id_1,
                    "name": recipient_name,
                    "phone": recipient_phone,
                    "remarks": recipient_remarks or "",
                }
            ],
            "isPODEnabled": False,
            "isRecipientSMSEnabled": False,
        }
        data = self._request("POST", "/v3/orders", body)
        return PlaceOrderResult(
            lalamove_order_id=data["orderId"],
            status=data.get("status", "ASSIGNING_DRIVER"),
            share_link=data.get("shareLink") or "",
        )

    def get_order(self, lalamove_order_id: str, created_at: datetime) -> OrderStatusResult:
        data      = self._request("GET", f"/v3/orders/{lalamove_order_id}")
        driver_id = data.get("driverId", "")

        # Driver details live at a separate endpoint; only fetch if assigned
        driver: dict = {}
        if driver_id:
            try:
                driver = self._request("GET", f"/v3/orders/{lalamove_order_id}/drivers/{driver_id}")
            except Exception:
                pass  # driver details optional — webhook will update when available

        return OrderStatusResult(
            status=data.get("status", "ASSIGNING_DRIVER"),
            driver_name=driver.get("name"),
            driver_phone=driver.get("phone"),
            driver_plate=driver.get("plateNumber"),
            tracking_url=data.get("trackingUrl"),
            share_link=data.get("shareLink"),
        )

    def cancel_order(self, lalamove_order_id: str) -> bool:
        try:
            self._request("DELETE", f"/v3/orders/{lalamove_order_id}", {})
            return True
        except Exception as e:
            logger.error(f"[LALAMOVE] cancel_order failed: {e}")
            return False

    def register_webhook(self, url: str) -> dict:
        """Register (or update) the webhook URL via PATCH /v3/webhook."""
        return self._request("PATCH", "/v3/webhook", {"url": url})

# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_service_instance: LalamoveService | None = None

def get_lalamove_service() -> LalamoveService:
    global _service_instance
    if _service_instance is None:
        _service_instance = LalamoveService()
    return _service_instance

def reset_lalamove_service():
    """Force re-instantiation on next call (used in tests)."""
    global _service_instance
    _service_instance = None
