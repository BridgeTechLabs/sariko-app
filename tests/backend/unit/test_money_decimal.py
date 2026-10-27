"""T89 (docs/dev/money-decimal/README.md): order money is Decimal end to end, and the DAOs hand
PostgREST strings, never Decimal or float. No DB, no network.

Run from tests/backend:  pytest unit/test_money_decimal.py
"""
import json
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import apis.sellers as sellers
from core.auth import verify_token
from dao.dao_order_items import DAOOrderItems
from dao.dao_orders import DAOOrders
from dao.dao_payments import DAOPayments
from dao.dao_refunds import DAORefunds
from services.lalamove_service import LalamoveService
from utils.pricing import order_amounts


def _line(qty, dish, variant=None):
    return {"quantity": qty, "food_items": {"id": "f", "name": "Adobo", "price": dish},
            "food_item_variants": {"name": "L", "price": variant} if variant else None}


def _check(a, subtotal, commission, vat, total):
    assert all(isinstance(v, Decimal) for v in a.values())
    assert a["subtotal"] == Decimal(subtotal)
    assert a["commission_amount"] == Decimal(commission)
    assert a["vat_amount"] == Decimal(vat)
    assert a["total_amount"] == Decimal(total)
    assert a["payout_amount"] + a["commission_amount"] + a["vat_amount"] == a["subtotal"]


# ─── TC-2: order money ──────────────────────────────────────────────────────
def test_tc2a_three_lines_with_variants():
    # 2 x 80.000 (variant) + 1 x 25.000 + 3 x 45.000 (variant) = 320.000
    cart = [_line(2, 50000, 80000), _line(1, 25000), _line(3, 40000, 45000)]
    a = order_amounts(cart, Decimal("0.17"), Decimal("0.08"), delivery_fee=25000)
    _check(a, "320000", "54400.00", "4352.00", "345000")
    assert a["payout_amount"] == Decimal("261248.00")


def test_tc2b_rate_override():
    a = order_amounts([_line(1, 33333)], Decimal("0.13"), Decimal("0.08"))
    _check(a, "33333", "4333.29", "346.66", "33333")   # 4333.29 x 0.08 = 346.6632
    assert a["payout_amount"] == Decimal("28653.05")


def test_tc2c_float_drift():
    a = order_amounts([_line(1, 33333)], Decimal("0.17"), Decimal("0.08"))
    _check(a, "33333", "5666.61", "453.33", "33333")   # float: 5666.610000000001
    # At today's rates (2-place commission rate, VAT 0.08) round(float) and HALF_UP agree on
    # every whole-VND subtotal; they part on a half cent, e.g. 1005 x 0.125 = 125.625:
    assert round(1005 * 0.125, 2) == 125.62
    a = order_amounts([_line(1, 1005)], Decimal("0.125"), Decimal("0.08"))
    _check(a, "1005", "125.63", "10.05", "1005")
    # ... and 175.95 x 0.1 = 17.595 (VAT on the commission):
    assert round(round(1035 * 0.17, 2) * 0.1, 2) == 17.59
    a = order_amounts([_line(1, 1035)], Decimal("0.17"), Decimal("0.1"))
    _check(a, "1035", "175.95", "17.60", "1035")


# ─── TC-3: what the DAOs send PostgREST ─────────────────────────────────────
class _Client:
    def __init__(self):
        self.sent = None

    def table(self, _):
        return self

    def insert(self, data):
        self.sent = data
        return self

    def execute(self):
        rows = self.sent if isinstance(self.sent, list) else [self.sent]
        return type("R", (), {"data": rows})()


def _dao(cls):
    dao = cls.__new__(cls)    # skip __init__: no Supabase client
    dao._supabase_client = _Client()
    dao._table_name = "t"
    return dao


def _plain(payload):
    json.dumps(payload)   # what httpx does; raises on Decimal
    values = payload if isinstance(payload, list) else [payload]
    assert not any(isinstance(v, (Decimal, float)) for row in values for v in row.values())


def test_tc3_create_order_payload():
    dao = _dao(DAOOrders)
    amounts = order_amounts([_line(1, 55000)], Decimal("0.17"), Decimal("0.08"), delivery_fee=25000)
    dao.create_order(user_id="u", seller_id="s", seller_user_id="su", commission_rate=Decimal("0.17"),
                     vat_rate=Decimal("0.08"), delivery_method="delivery", delivery_fee=25000, **amounts)
    sent = dao._supabase_client.sent
    _plain(sent)
    assert {k: sent[k] for k in amounts} == {
        "subtotal": "55000", "total_amount": "80000", "commission_amount": "9350.00",
        "vat_amount": "748.00", "payout_amount": "44902.00"}
    assert (sent["commission_rate"], sent["vat_rate"], sent["delivery_fee"]) == ("0.17", "0.08", 25000)


def test_tc3_payment_refund_order_items_payload():
    pay = _dao(DAOPayments)
    pay.create_payment(order_id="o", method="vnpay", amount=Decimal("65000.00"), status="succeeded", transaction_ref="t")
    _plain(pay._supabase_client.sent)
    assert pay._supabase_client.sent["amount"] == "65000.00"

    ref = _dao(DAORefunds)
    ref.create_refund(order_id="o", amount=65000, reason="late_payment")        # IPN: int VND
    assert ref._supabase_client.sent["amount"] == "65000"
    ref.create_refund_for_order({"id": "o", "payment_status": "paid", "total_amount": 65000.0}, "seller_cancel")
    _plain(ref._supabase_client.sent)
    assert ref._supabase_client.sent["amount"] == "65000.0"

    items = _dao(DAOOrderItems)
    items.create_order_items_from_cart("o", [_line(2, 50000, 80000), _line(1, 25000)])
    _plain(items._supabase_client.sent)
    assert [r["price_snapshot"] for r in items._supabase_client.sent] == ["80000", "25000"]


# ─── TC-5: Lalamove quotation total ─────────────────────────────────────────
@pytest.mark.parametrize("total", ["35000", "35000.0", 35000])
def test_tc5_quotation_total_is_int(total):
    svc = LalamoveService.__new__(LalamoveService)
    svc._request = lambda *a: {"quotationId": "q", "stops": [{"stopId": "a"}, {"stopId": "b"}],
                               "priceBreakdown": {"total": total, "currency": "VND"},
                               "distance": {"value": "3200"}}
    fee = svc.get_quotation(10.77, 106.70, "Q1", 10.73, 106.72, "D7").total_fee
    assert fee == 35000 and type(fee) is int


# ─── TC-6: dish / variant price is whole VND ────────────────────────────────
@pytest.fixture
def seller_client(monkeypatch):
    class FakeItems:
        def create(self, seller_id, fields):
            return fields

        def read_owned_by_seller(self, item_id, seller_id):
            return True

    class FakeVariants:
        def create(self, item_id, fields):
            return fields

    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "seller")
    monkeypatch.setattr(sellers, "DAOFoodItems", FakeItems)
    monkeypatch.setattr(sellers, "DAOFoodItemVariants", FakeVariants)
    app = FastAPI()
    app.include_router(sellers.router)
    app.dependency_overrides[verify_token] = lambda: {"id": "u"}
    return TestClient(app)


@pytest.mark.parametrize("path,key,body", [
    ("/sellers/me/menu/items", "item", {"name": "Adobo"}),
    ("/sellers/me/menu/items/i/variants", "variant", {"name": "L"}),
])
def test_tc6_price_whole_vnd(seller_client, path, key, body):
    res = seller_client.post(path, json={**body, "price": 45000})
    assert res.status_code == 200
    assert res.json()[key]["price"] == 45000 and res.json()[key]["price_text"] == "45.000 ₫"
    assert seller_client.post(path, json={**body, "price": 45000.5}).status_code == 422
