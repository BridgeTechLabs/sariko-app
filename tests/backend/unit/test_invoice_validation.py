"""services/invoice_validation.py — what stops a commission invoice before anything is saved.

Why this matters: an e-invoice is a legal document — a field VNPAY would reject, or one we would
have to cut (a wrong ID, account number or name), must stop the invoice with a clear reason.
"""
import pytest

from services.invoice_validation import InvoiceValidationService

APPLICATION = {"tax_code": "0312345678", "first_name": "Maria", "last_name": "Santos",
               "residential_address": "12 Nguyễn Huệ, Q1", "phone": "+84901234567",
               "email": "maria@example.com", "id_type": "cccd", "id_number": "079123456789",
               "bank_name": "Vietcombank", "bank_account_number": "1234567890", "nationality": "Philippines"}


validator = InvoiceValidationService()


def order(order_id, seller_id="s1", payment_status="paid", commission_amount=19000):
    return {"id": order_id, "seller_id": seller_id, "payment_status": payment_status,
            "commission_amount": commission_amount}


def test_valid_orders_come_back_in_the_callers_order():
    assert [o["id"] for o in validator.validate_orders(["o1", "o2"], [order("o2"), order("o1")])] == ["o1", "o2"]


@pytest.mark.parametrize("found, message", [
    ([order("o1")], "Orders not found: \\['o2'\\]"),
    ([order("o1"), order("o2", payment_status="pending")], "Orders not paid: \\['o2'\\]"),
    ([order("o1"), order("o2", commission_amount=0)], "Orders without commission: \\['o2'\\]"),
    ([order("o1"), order("o2", seller_id="s2")], "more than one seller"),
])
def test_invalid_orders_raise(found, message):
    with pytest.raises(ValueError, match=message):
        validator.validate_orders(["o1", "o2"], found)


def test_valid_buyer_passes():
    validator.validate_buyer("s1", APPLICATION)
    validator.validate_buyer("s1", {**APPLICATION, "id_type": "passport", "id_number": "P" * 20})


def test_buyer_without_application_raises():
    with pytest.raises(ValueError, match="no approved onboarding application"):
        validator.validate_buyer("s1", None)


@pytest.mark.parametrize("tax_code", [None, ""])
def test_buyer_without_tax_code_raises(tax_code):
    with pytest.raises(ValueError, match="buyerTaxCode is empty"):
        validator.validate_buyer("s1", {**APPLICATION, "tax_code": tax_code})


@pytest.mark.parametrize("changes, field", [
    ({"tax_code": "0" * 15}, "buyerTaxCode"),
    ({"first_name": "M" * 100}, "buyerName"),
    ({"residential_address": "a" * 401}, "buyerAddress"),
    ({"phone": "0" * 21}, "buyerPhoneNumber"),
    ({"email": "m" * 41 + "@example.com"}, "buyerEmail"),
    ({"id_number": "0" * 13}, "buyerIdNumber"),                                   # CCCD: 12
    ({"id_type": "passport", "id_number": "P" * 21}, "buyerPassportNumber"),      # passport: 20
    ({"bank_name": "B" * 401}, "buyerBankName"),
    ({"bank_account_number": "1" * 31}, "buyerBankAccountNumber"),
    ({"nationality": "K" * 51}, "buyerNationality"),
])
def test_buyer_field_over_viiapi_limit_raises(changes, field):
    with pytest.raises(ValueError, match=f"{field} is longer than"):
        validator.validate_buyer("s1", {**APPLICATION, **changes})


def test_buyer_lists_every_problem_at_once():
    with pytest.raises(ValueError) as e:
        validator.validate_buyer("s1", {**APPLICATION, "tax_code": None, "email": "m" * 51, "bank_account_number": "1" * 31})
    assert "buyerTaxCode is empty" in str(e.value)
    assert "buyerEmail" in str(e.value)
    assert "buyerBankAccountNumber" in str(e.value)
