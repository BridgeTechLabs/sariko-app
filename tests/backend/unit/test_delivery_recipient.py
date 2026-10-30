"""docs/dev/delivery-recipient R3: the Lalamove driver gets the order's receiver and note, the buyer's
profile only for orders placed before. Both bookings (seller marks ready, seller rebooks) use one helper.
No DB, no network.

Run from tests/backend:  pytest unit/test_delivery_recipient.py
"""
import pytest
from fastapi import HTTPException

from apis import deliveries, sellers
from apis.deliveries import lalamove_recipient
from pydantic import ValidationError

from schemas import Schema
from services.lalamove_service import PlaceOrderResult, QuotationResult

BUYER = {"name": "Buyer", "phone": "0911111111", "email": "b@x.vn"}
SELLER = {"store_name": "Lola", "address": "30 Ton That Thiep", "lat": 10.77, "lon": 106.70, "phone": "0901234567"}
WITH_RECEIVER = {"receiver_name": "Maria", "receiver_phone": "+84902222222", "delivery_note": "Tầng 3 · cổng B"}
EXPECTED = {"recipient_name": "Maria", "recipient_phone": "+84902222222",
            "recipient_remarks": "Tầng 3 · cổng B | 12 Nguyen Hue, Q1"}


def full_order(**receiver):
    return {"id": "order-1", "status": "confirmed", "delivery_method": "delivery", "delivery_address": "12 Nguyen Hue, Q1",
            "delivery_lat": 10.77, "delivery_lon": 106.70, "seller_profiles": SELLER, "users": BUYER, **receiver}


def test_tc5_order_receiver_and_note():
    assert lalamove_recipient(full_order(**WITH_RECEIVER)) == EXPECTED


def test_tc6_old_order_uses_buyer_profile():
    assert lalamove_recipient(full_order()) == {
        "recipient_name": "Buyer", "recipient_phone": "+84911111111", "recipient_remarks": "12 Nguyen Hue, Q1"}


def test_tc14_name_without_phone_uses_profile_phone():
    assert lalamove_recipient(full_order(receiver_name="Maria")) == {
        "recipient_name": "Maria", "recipient_phone": "+84911111111", "recipient_remarks": "12 Nguyen Hue, Q1"}


def test_tc17_receiver_without_note_sends_the_address_only():
    order = {**full_order(receiver_name="Maria", receiver_phone="+84902222222"), "delivery_address": "Lô A | 12 Nguyen Hue"}
    assert lalamove_recipient(order)["recipient_remarks"] == "Lô A | 12 Nguyen Hue"


def test_bad_stored_receiver_phone_names_the_receiver():
    with pytest.raises(HTTPException) as e:
        lalamove_recipient(full_order(receiver_phone="123"))
    assert e.value.detail["code"] == "receiver_phone_invalid"


@pytest.mark.parametrize("field, size", [("receiver_name", 101), ("phone_number", 21), ("street_name", 201), ("note", 251)])
@pytest.mark.parametrize("schema", [Schema.RequestCreateUserAddress, Schema.RequestUpdateUserAddress])
def test_address_fields_fit_the_order(schema, field, size):
    """street_name + " · " + note stays under the order's delivery_note limit (500)."""
    body = {"address": "12 Nguyen Hue", "receiver_name": "Maria", "phone_number": "0902222222", "lat": 10.7, "lon": 106.7}
    with pytest.raises(ValidationError):
        schema(**{**body, field: "x" * size})


def test_tc6_old_order_bad_buyer_phone():
    with pytest.raises(HTTPException) as e:
        lalamove_recipient({**full_order(), "users": {**BUYER, "phone": "123"}})
    assert e.value.status_code == 400
    assert e.value.detail["code"] == "buyer_phone_invalid"


class FakeLalamove:
    def __init__(self):
        self.placed = []

    def get_quotation(self, **kw):
        return QuotationResult(quotation_id="q", stop_id_0="s0", stop_id_1="s1", total_fee=25000, currency="VND", distance_km=3)

    def place_order(self, **kw):
        self.placed.append(kw)
        return PlaceOrderResult(lalamove_order_id="lm-1", status="ASSIGNING_DRIVER", share_link="")


class FakeDeliveries:
    def read_delivery_by_order_id(self, order_id):
        return {"id": "d-1", "status": "CANCELLED", "rebook_count": 0}

    def create_delivery(self, **kw):
        pass

    def update_delivery(self, *args):
        pass


def fake_orders(order):
    class FakeOrders:
        def read_order_by_id_for_seller(self, order_id, seller_id):
            return order

        def read_order_with_seller_coords(self, order_id):
            return order

        def update_order_status(self, *args, **kwargs):
            return order
    return FakeOrders


class FakeConfig:
    def get_positive_int(self, key, default):
        return default


@pytest.mark.parametrize("receiver, recipient_name", [(WITH_RECEIVER, "Maria"), ({}, "Buyer")])
def test_tc5_tc6_seller_ready_books_the_receiver(monkeypatch, caplog, receiver, recipient_name):
    lalamove = FakeLalamove()
    monkeypatch.setattr(sellers, "_get_seller_id", lambda user: "seller-1")
    monkeypatch.setattr(sellers, "DAOOrders", fake_orders(full_order(**receiver)))
    monkeypatch.setattr(sellers, "DAOAdminConfig", FakeConfig)
    monkeypatch.setattr("services.lalamove_service.get_lalamove_service", lambda: lalamove)
    monkeypatch.setattr("dao.dao_deliveries.DAODeliveries", FakeDeliveries)

    sellers.update_seller_order_status("order-1", Schema.RequestUpdateOrderStatus(status="ready"), user={"id": "u"})

    [placed] = lalamove.placed
    assert placed["recipient_name"] == recipient_name
    if receiver:
        assert {k: placed[k] for k in EXPECTED} == EXPECTED
    assert placed["recipient_phone"] not in caplog.text  # TC-24: the log keeps the last 4 digits only
    assert placed["recipient_phone"][-4:] in caplog.text


def test_tc7_rebook_books_the_receiver(monkeypatch):
    lalamove = FakeLalamove()

    class FakeSellerProfiles:
        def read_seller_profile_by_user_id(self, user_id):
            return {"id": "seller-1"}

    monkeypatch.setattr(deliveries, "DAOSellerProfiles", FakeSellerProfiles)
    monkeypatch.setattr(deliveries, "DAOOrders", fake_orders({**full_order(**WITH_RECEIVER), "status": "ready"}))
    monkeypatch.setattr(deliveries, "DAODeliveries", FakeDeliveries)
    monkeypatch.setattr(deliveries, "rebook_max", lambda: 3)
    monkeypatch.setattr(deliveries, "get_lalamove_service", lambda: lalamove)

    assert deliveries.rebook_delivery("order-1", user={"id": "u"}) == {"success": True}
    [placed] = lalamove.placed
    assert {k: placed[k] for k in EXPECTED} == EXPECTED
