"""R1 (docs/dev/order-cancel-refund.md): the server quotes the delivery fee; the client's fee is
only checked against it. No DB, no network.

Run from tests/backend:  pytest unit/test_order_delivery_fee.py
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

import apis.orders as orders
from schemas import Schema
from services.lalamove_service import QuotationResult

SUBTOTAL = 100000  # 2 x 50.000
created = []       # kwargs of every DAOOrders.create_order call


class FakeCartItems:
    def read_cart_items_by_user_id(self, user_id):
        return {"id": "cart", "seller_id": "seller", "cart_items": [
            {"quantity": 2, "food_items": {"name": "Adobo", "price": 50000, "is_available": True, "preorder_day": 1},
             "food_item_variants": None},
        ]}


class FakeOrders:
    def read_orders_by_user_id(self, user_id):
        return []

    def create_order(self, **kw):
        created.append(kw)
        return {"id": "order", **kw}


class FakeSellers:
    def read_seller_order_info(self, seller_id):
        return {"user_id": "seller-user", "is_open": True, "commission_rate": Decimal("0.1"),
                "address": "Q1", "lat": 10.77, "lon": 106.70}


class FakeVat:
    def get_tax_rate(self, _):
        return Decimal("0.1")


class FakeOrderItems:
    def create_order_items_from_cart(self, **kw):
        pass


class FakeCarts:
    def delete_cart(self, **kw):
        pass


class FakeLalamove:
    def __init__(self, fee):
        self.fee = fee

    def get_quotation(self, **kw):
        if self.fee is None:
            raise RuntimeError("Lalamove 500")
        return QuotationResult(quotation_id=f"q-{self.fee}", stop_id_0="s0", stop_id_1="s1",
                               total_fee=self.fee, currency="VND", distance_km=3.2)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    created.clear()
    for name, fake in [("DAOCartItems", FakeCartItems), ("DAOOrders", FakeOrders),
                       ("DAOSellerProfiles", FakeSellers), ("DAOAdminConfig", FakeVat),
                       ("DAOOrderItems", FakeOrderItems), ("DAOCarts", FakeCarts)]:
        monkeypatch.setattr(orders, name, fake)


def place(monkeypatch, server_fee, client_fee):
    monkeypatch.setattr(orders, "get_lalamove_service", lambda: FakeLalamove(server_fee))
    req = Schema.RequestCreateOrder(delivery_method="delivery", delivery_address="D7",
                                    delivery_lat=10.73, delivery_lon=106.72,
                                    delivery_fee=client_fee, quotation_id="client-q",
                                    # the cart's dish is a 1-day pre-order (T127)
                                    delivery_appointment=datetime.now(timezone.utc) + timedelta(days=2))
    return orders.create_order(req, user={"id": "buyer"})


def test_r1_1_client_fee_zero_is_rejected(monkeypatch):
    with pytest.raises(HTTPException) as e:
        place(monkeypatch, server_fee=25000, client_fee=0)
    assert e.value.status_code == 409
    assert e.value.detail["delivery_fee"] == 25000
    assert created == []


def test_r1_2_matching_fee_creates_order_with_server_values(monkeypatch):
    res = place(monkeypatch, server_fee=25000, client_fee=25000)
    assert res["success"]
    [order] = created
    assert order["delivery_fee"] == 25000
    assert order["total_amount"] == SUBTOTAL + 25000
    assert order["quotation_id"] == "q-25000"  # server's quote, not the client's


def test_r1_3_fee_changed_returns_new_fee(monkeypatch):
    with pytest.raises(HTTPException) as e:
        place(monkeypatch, server_fee=28000, client_fee=25000)
    assert e.value.status_code == 409
    assert e.value.detail["delivery_fee"] == 28000
    assert e.value.detail["quotation_id"] == "q-28000"
    assert created == []


def test_r1_4_quote_failure_creates_nothing(monkeypatch):
    with pytest.raises(HTTPException) as e:
        place(monkeypatch, server_fee=None, client_fee=25000)
    assert e.value.status_code == 502
    assert "delivery fee" in e.value.detail
    assert created == []  # no order → nothing to pay
