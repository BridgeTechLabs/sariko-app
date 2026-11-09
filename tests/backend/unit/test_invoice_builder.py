"""services/vnpay/invoices/invoice_builder.py — an order → Sariko's commission VAT invoice to the seller.

Why this matters: an e-invoice is a legal document — amounts must match the order snapshot
and the tax rate must be one viiAPI accepts.
"""
from decimal import Decimal

import pytest

from services.vnpay.invoices.invoice_builder import build_commission_invoice, tax_rate_label
from services.vnpay.invoices import TaxRateCode, TaxType

APPLICATION = {"tax_code": "0312345678", "full_name": "Maria Santos",
               "residential_address": "12 Nguyễn Huệ, Q1", "phone": "+84901234567",
               "email": "maria@example.com", "id_type": "cccd",
               "id_number": "079123456789", "bank_name": "Vietcombank", "bank_account_number": "1234567890",
               "nationality": "Philippines"}


def order(order_id, commission, vat_rate, vat):
    return {"id": order_id, "seller_id": "s1", "payment_status": "paid", "commission_amount": commission,
            "vat_rate": vat_rate, "vat_amount": vat}


@pytest.mark.parametrize("rate,label", [
    (0.1, "10%"), (0.10, "10%"), (0.08, "8%"), (0.05, "5%"), (0, "0%"),   # TaxRateCode values
    (0.075, "KHAC:7.50%"), (0.07, "KHAC:7.00%"), (0.0526, "KHAC:5.26%"),  # no code of their own
])
def test_tax_rate_label(rate, label):
    assert tax_rate_label(rate) == label


def test_tax_rate_codes_match_the_doc_and_pass_model_validation():
    assert [c.value for c in TaxRateCode] == ["0%", "5%", "8%", "10%", "KCT", "KKKNT", "KHAC"]
    for code in TaxRateCode:
        TaxType(tax=code.value, amount=0, tax_amount=0)


def test_one_line_for_the_order_and_totals_from_snapshot():
    inv = build_commission_invoice(order("11111111-aaaa", 19000, 0.1, 1900), "req-1", "0102030405", "C26TSA", "VND", APPLICATION).to_wire()
    assert inv["taxCode"] == "0102030405"
    assert inv["autoRelease"] is False
    assert inv["autoSign"] is False
    assert inv["invoice"]["currencyUnit"] == "VND"
    assert inv["invoice"]["currencyExchangeRate"] == Decimal(1)
    assert inv["invoice"]["discount"] is False
    assert "totalDiscountAmount" not in inv["invoice"]
    assert inv["invoice"]["isPetrolInvoice"] is False
    assert inv["invoice"]["isSendMail"] is False
    assert inv["invoice"]["financialLeasingInvoice"] is False
    assert inv["invoice"]["isSellerGasolineBusiness"] is False
    assert inv["invoice"]["isAssetOwnershipRegistration"] is False
    assert inv["invoice"]["hasAuctionAuthorityInfo"] is False
    assert inv["invoice"]["createdBy"] == "Sariko System"
    body = inv["invoice"]
    assert body["requestId"] == "req-1"
    assert [p["ordinalNumber"] for p in body["products"]] == [1]
    assert body["products"][0]["name"] == "Phí dịch vụ nền tảng Sariko - đơn hàng 11111111-aaaa"  # full order id
    assert body["products"][0]["property"] == 1 and body["products"][0]["quantity"] == Decimal(1)
    assert body["products"][0]["amountAfterTax"] == Decimal("20900")
    assert body["totalAmount"] == Decimal("19000")
    assert body["totalTaxAmount"] == Decimal("1900")
    assert body["totalAmountAfterTax"] == Decimal("20900")
    assert body["totalPaymentInWord"] == "Hai mươi nghìn chín trăm đồng"
    assert body["taxTypes"] == [{"tax": "10%", "amount": Decimal("19000"), "taxAmount": Decimal("1900")}]
    assert body["buyerCustomerCode"] == "s1"
    assert body["buyerTaxCode"] == "0312345678"
    assert body["buyerName"] == "Maria Santos"
    assert body["buyerFullName"] == "Maria Santos"
    assert body["buyerAddress"] == "12 Nguyễn Huệ, Q1"
    assert body["buyerPhoneNumber"] == "+84901234567"
    assert body["buyerIdNumber"] == "079123456789"
    assert "buyerPassportNumber" not in body
    assert body["buyerBankName"] == "Vietcombank"
    assert body["buyerBankAccountNumber"] == "1234567890"
    assert body["buyerNationalityCode"] == "PH"
    assert body["buyerNationality"] == "Philippines"
    assert body["buyerEmail"] == "maria@example.com"


def test_tax_types_carries_the_orders_rate():
    body = build_commission_invoice(order("o1", 10000, 0.08, 800), "req-1", "0102030405", "C26TSA", "VND",
                                    APPLICATION).to_wire()["invoice"]
    assert body["taxTypes"] == [{"tax": "8%", "amount": Decimal("10000"), "taxAmount": Decimal("800")}]


@pytest.mark.parametrize("id_type, id_number, id_field, passport_field", [
    ("cccd", "079123456789", "079123456789", None),
    ("passport", "P1234567A", None, "P1234567A"),
])
def test_id_goes_to_id_or_passport_field_by_id_type(id_type, id_number, id_field, passport_field):
    application = {**APPLICATION, "id_type": id_type, "id_number": id_number}
    body = build_commission_invoice(order("o1", 19000, 0.1, 1900), "req-1", "0102030405", "C26TSA", "VND",
                                    application).to_wire()["invoice"]
    assert body.get("buyerIdNumber") == id_field
    assert body.get("buyerPassportNumber") == passport_field


@pytest.mark.parametrize("nationality, code, name", [
    ("Philippines", "PH", "Philippines"),
    ("Vietnam", "VN", "Vietnam"),
    ("Korean", None, "Korean"),                 # "Other" free text: no code, name as typed
])
def test_nationality_code_only_for_known_countries(nationality, code, name):
    application = {**APPLICATION, "nationality": nationality}
    body = build_commission_invoice(order("o1", 19000, 0.1, 1900), "req-1", "0102030405", "C26TSA", "VND",
                                    application).to_wire()["invoice"]
    assert body.get("buyerNationalityCode") == code
    assert body.get("buyerNationality") == name


@pytest.mark.parametrize("commission, vat, amount, tax_amount, words", [
    ("2345.55", "234.56", "2346", "235", "Hai nghìn năm trăm tám mươi mốt đồng"),   # .55 / .56 → up
    ("1000.49", "100.05", "1000", "100", "Một nghìn một trăm đồng"),                 # .49 / .05 → down
])
def test_amounts_are_rounded_half_up_so_totals_and_words_are_whole(commission, vat, amount, tax_amount, words):
    body = build_commission_invoice(order("o1", commission, 0.1, vat), "req-1", "0102030405", "C26TSA", "VND",
                                    APPLICATION).to_wire()["invoice"]
    after_tax = Decimal(amount) + Decimal(tax_amount)
    assert [(p["amount"], p["taxAmount"], p["amountAfterTax"]) for p in body["products"]] == [
        (Decimal(amount), Decimal(tax_amount), after_tax)]
    assert (body["totalAmount"], body["totalTaxAmount"], body["totalAmountAfterTax"]) == (
        Decimal(amount), Decimal(tax_amount), after_tax)
    assert body["taxTypes"] == [{"tax": "10%", "amount": Decimal(amount), "taxAmount": Decimal(tax_amount)}]
    assert body["totalPaymentInWord"] == words
