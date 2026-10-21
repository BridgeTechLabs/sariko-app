"""Integration tests for GET /payments/payment-status/{order_id}.

This endpoint is polled every 3s from PaymentResult.vue after VNPay redirect.

Why this exists: catch the exact bug we just hit — frontend calling without auth
header, or backend losing auth check, would silently break payment flow.
"""
from unittest.mock import patch


class _FakeOrderDAO:
    def __init__(self, order):
        self._order = order
        self.last_user_id = None

    def read_order_by_id(self, order_id, user_id):
        # Mirrors real DAO: filters by user_id (RLS-style ownership check)
        self.last_user_id = user_id
        if self._order and self._order["id"] == order_id and self._order["user_id"] == user_id:
            return self._order
        return None


def test_payment_status_requires_auth(fastapi_client):
    """No Authorization header → 403 'Not authenticated'.

    This was the production bug: frontend used raw axios (no token) → 403 every poll.
    """
    res = fastapi_client.get("/payments/payment-status/some-order-id")

    assert res.status_code == 403
    assert res.json()["detail"] == "Not authenticated"


def test_payment_status_returns_status_for_owner(fastapi_client, monkeypatch):
    """Authenticated buyer + owns the order → returns payment_status."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"
    user_id = "user-uuid-123"

    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "user_id": user_id,
        "payment_status": "pending",
    })
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)
    monkeypatch.setattr("apis.payments.DAOAdminConfig", lambda: type("C", (), {"get_positive_int": lambda self, k, d: d})())

    # Bypass JWT verification — just inject a user dict
    from apis.payments import router as payments_router
    from core.auth import verify_token
    fastapi_client.app.dependency_overrides[verify_token] = lambda: {"id": user_id}

    try:
        res = fastapi_client.get(f"/payments/payment-status/{order_id}")
        assert res.status_code == 200
        assert res.json()["payment_status"] == "pending"
        assert res.json()["wait_seconds"] == 90     # payment_result_wait_seconds default (T125)
        assert fake_orders.last_user_id == user_id, \
            "DAO must be called with authenticated user_id (ownership check)"
    finally:
        fastapi_client.app.dependency_overrides.clear()


def test_payment_status_404_when_not_owner(fastapi_client, monkeypatch):
    """Authenticated user but order belongs to someone else → 404 (don't leak existence)."""
    order_id = "abc12345-678a-4bcd-9012-345678901234"

    fake_orders = _FakeOrderDAO({
        "id": order_id,
        "user_id": "other-user",
        "payment_status": "paid",
    })
    monkeypatch.setattr("apis.payments.DAOOrders", lambda: fake_orders)

    from core.auth import verify_token
    fastapi_client.app.dependency_overrides[verify_token] = lambda: {"id": "current-user"}

    try:
        res = fastapi_client.get(f"/payments/payment-status/{order_id}")
        assert res.status_code == 404
    finally:
        fastapi_client.app.dependency_overrides.clear()
