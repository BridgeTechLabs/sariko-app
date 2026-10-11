"""Integration tests for Lalamove delivery webhook.

Why this matters: webhook drives the order status machine for delivery orders.
If signature verify is wrong → either we accept fake webhooks (data corruption)
or reject real ones (orders stuck in 'ready' forever).
"""
import hmac
import hashlib
import json


def _sign(secret: str, timestamp: int, path: str, raw_data_str: str) -> str:
    """Mirror of webhook handler signature scheme."""
    raw = f"{timestamp}\r\nPOST\r\n{path}\r\n\r\n{raw_data_str}"
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _make_webhook_body(api_key: str, secret: str, event_type: str, data_dict: dict, timestamp: int = 1735689600000):
    """Build a webhook body with valid signature. Returns (body_dict, raw_body_bytes)."""
    # IMPORTANT: handler extracts the raw "data" substring from the body bytes,
    # so we must serialize once with stable formatting and pass the bytes directly.
    data_json = json.dumps(data_dict, separators=(",", ":"))
    path = "/deliveries/webhook"
    signature = _sign(secret, timestamp, path, data_json)

    body = {
        "apiKey": api_key,
        "timestamp": timestamp,
        "signature": signature,
        "eventType": event_type,
        "data": data_dict,
    }
    # Serialize with the same formatting so the handler's substring extraction matches
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    return body, raw


# ─── Mocks ───────────────────────────────────────────────────────────────────
class _FakeDeliveryDAO:
    def __init__(self, delivery):
        self._delivery = delivery
        self.last_update = None

    def read_delivery_by_lalamove_order_id(self, lalamove_id):
        if self._delivery and self._delivery.get("lalamove_order_id") == lalamove_id:
            return self._delivery
        return None

    def update_delivery(self, delivery_id, update_data):
        self.last_update = update_data
        if self._delivery:
            self._delivery.update(update_data)


class _FakeOrderDAO:
    def __init__(self, order):
        self._order = order
        self.last_status = None

    def read_order_by_id_raw(self, order_id):
        if self._order and self._order["id"] == order_id:
            return self._order
        return None

    def update_order_status(self, order_id, status):
        self.last_status = status
        if self._order:
            self._order["status"] = status
        return self._order


# ─── Tests ───────────────────────────────────────────────────────────────────
def test_webhook_completed_marks_order_done(fastapi_client, lalamove_secret, lalamove_api_key, monkeypatch):
    """COMPLETED webhook → delivery status updated AND order status → 'done'."""
    delivery = {
        "id": "del-uuid",
        "order_id": "ord-uuid",
        "lalamove_order_id": "LM12345",
        "status": "PICKED_UP",
    }
    order = {"id": "ord-uuid", "status": "ready"}
    fake_del = _FakeDeliveryDAO(delivery)
    fake_ord = _FakeOrderDAO(order)
    monkeypatch.setattr("apis.deliveries.DAODeliveries", lambda: fake_del)
    monkeypatch.setattr("apis.deliveries.DAOOrders", lambda: fake_ord)
    notified = []
    monkeypatch.setattr("apis.deliveries.push_service.notify_seller_delivered", notified.append)

    body, raw = _make_webhook_body(
        lalamove_api_key, lalamove_secret,
        event_type="ORDER_STATUS_CHANGED",
        data_dict={"order": {"orderId": "LM12345", "status": "COMPLETED"}},
    )
    res = fastapi_client.post(
        "/deliveries/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 200
    assert res.json()["success"] is True
    assert fake_del.last_update["status"] == "COMPLETED"
    assert fake_ord.last_status == "done"
    assert [o["id"] for o in notified] == ["ord-uuid"], "Seller must be told the driver delivered"


def test_webhook_terminal_status_clears_driver_and_marks_failed(
    fastapi_client, lalamove_secret, lalamove_api_key, monkeypatch
):
    """REJECTED → delivery driver fields cleared AND order → 'delivery_failed'.
    Critical: buyer UI hides driver info on terminal statuses."""
    delivery = {
        "id": "del-uuid",
        "order_id": "ord-uuid",
        "lalamove_order_id": "LM99",
        "status": "ASSIGNING_DRIVER",
        "driver_name": "Old Driver",
        "driver_phone": "0900000000",
    }
    order = {"id": "ord-uuid", "status": "ready"}
    fake_del = _FakeDeliveryDAO(delivery)
    fake_ord = _FakeOrderDAO(order)
    monkeypatch.setattr("apis.deliveries.DAODeliveries", lambda: fake_del)
    monkeypatch.setattr("apis.deliveries.DAOOrders", lambda: fake_ord)

    body, raw = _make_webhook_body(
        lalamove_api_key, lalamove_secret,
        event_type="ORDER_STATUS_CHANGED",
        data_dict={"order": {"orderId": "LM99", "status": "REJECTED"}},
    )
    res = fastapi_client.post(
        "/deliveries/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 200
    assert fake_del.last_update["status"] == "REJECTED"
    assert fake_del.last_update["driver_name"] is None
    assert fake_del.last_update["driver_phone"] is None
    assert fake_ord.last_status == "delivery_failed"


def test_webhook_invalid_signature_rejected(
    fastapi_client, lalamove_secret, lalamove_api_key, monkeypatch
):
    """Wrong signature → reject, no DB write."""
    delivery = {"id": "del-uuid", "order_id": "ord-uuid", "lalamove_order_id": "LM12345", "status": "PICKED_UP"}
    fake_del = _FakeDeliveryDAO(delivery)
    fake_ord = _FakeOrderDAO({"id": "ord-uuid", "status": "ready"})
    monkeypatch.setattr("apis.deliveries.DAODeliveries", lambda: fake_del)
    monkeypatch.setattr("apis.deliveries.DAOOrders", lambda: fake_ord)

    body, raw = _make_webhook_body(
        lalamove_api_key, lalamove_secret,
        event_type="ORDER_STATUS_CHANGED",
        data_dict={"order": {"orderId": "LM12345", "status": "COMPLETED"}},
    )
    # Tamper the body to invalidate the signature
    tampered = raw.replace(b"COMPLETED", b"REJECTED")

    res = fastapi_client.post(
        "/deliveries/webhook",
        content=tampered,
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid signature"
    assert fake_del.last_update is None, "Must NOT update on invalid signature"
    assert fake_ord.last_status is None


def test_webhook_unknown_lalamove_order_silently_ok(
    fastapi_client, lalamove_secret, lalamove_api_key, monkeypatch
):
    """Unknown lalamove_order_id → 200 success (no retry storm) but no DB write."""
    fake_del = _FakeDeliveryDAO(None)
    fake_ord = _FakeOrderDAO(None)
    monkeypatch.setattr("apis.deliveries.DAODeliveries", lambda: fake_del)
    monkeypatch.setattr("apis.deliveries.DAOOrders", lambda: fake_ord)

    body, raw = _make_webhook_body(
        lalamove_api_key, lalamove_secret,
        event_type="ORDER_STATUS_CHANGED",
        data_dict={"order": {"orderId": "LM_UNKNOWN", "status": "COMPLETED"}},
    )
    res = fastapi_client.post(
        "/deliveries/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 200
    assert res.json()["success"] is True
    assert fake_del.last_update is None
    assert fake_ord.last_status is None


def test_webhook_registration_ping_ok_without_db_write(fastapi_client, monkeypatch):
    """Lalamove's URL verification has no apiKey/signature → 200, so the Portal accepts the URL.
    Even if it carries event data, nothing is written."""
    fake_del = _FakeDeliveryDAO({"id": "del-uuid", "order_id": "ord-uuid", "lalamove_order_id": "LM12345", "status": "PICKED_UP"})
    fake_ord = _FakeOrderDAO({"id": "ord-uuid", "status": "ready"})
    monkeypatch.setattr("apis.deliveries.DAODeliveries", lambda: fake_del)
    monkeypatch.setattr("apis.deliveries.DAOOrders", lambda: fake_ord)

    for body in ({}, {"eventType": "ORDER_STATUS_CHANGED", "data": {"order": {"orderId": "LM12345", "status": "REJECTED"}}}):
        res = fastapi_client.post("/deliveries/webhook", json=body)
        assert res.status_code == 200
        assert fake_del.last_update is None, "Unsigned request must NOT update the delivery"
        assert fake_ord.last_status is None
