"""
Order → VNPAY Invoice payload.

Sariko invoices the seller for its platform commission on one order: a single line =
orders.commission_amount, VAT = orders.vat_amount at orders.vat_rate (all snapshotted when the
order was created). taxTypes has one entry per rate used.
"""
from decimal import ROUND_HALF_UP, Decimal

from core.vn_time import vn_today
from core.vnd_words import vnd_in_words

from .models import OriginalVatInvoice, OriginalVatInvoiceRequest, TaxRateCode, TaxType, VatProduct
from .models.enums.invoice_constants import (
    CREATED_BY,
    CURRENCY_EXCHANGE_RATE,
    NATIONALITY_CODES,
    PAYMENT_METHOD,
)


def tax_rate_label(vat_rate) -> str:
    """0.1 → "10%" (TaxRateCode.RATE_10); a rate with no code of its own → "KHAC:xx.xx%" (OTHER).
    orders.vat_rate is always a number, so NON_TAX / NOT_DECLARED never come out of here."""
    percent = Decimal(str(vat_rate)) * 100
    if percent == percent.to_integral_value() and f"{int(percent)}%" in {code.value for code in TaxRateCode}:
        return TaxRateCode(f"{int(percent)}%").value
    return f"{TaxRateCode.OTHER.value}:{percent:.2f}%"


def buyer_legal_name(application: dict) -> str:
    """Seller's name as on the passport / CCCD, used for buyerName and buyerFullName."""
    return application["full_name"]


def _round_vnd(amount) -> Decimal:
    """Whole đồng, half up (2345.55 → 2346). Orders keep 2 decimals; a VND invoice has none."""
    return Decimal(str(amount)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _commission_line(ordinal: int, order: dict) -> VatProduct:
    """The order's invoice line: its commission, before tax, no discount.
    Commission and VAT are rounded per line, so every total (sums of lines) is whole too and
    the amount in words matches the figures; the invoice can differ from orders by < 1 đ per line."""
    commission = _round_vnd(order["commission_amount"])
    vat = _round_vnd(order["vat_amount"])
    return VatProduct(
        ordinal_number=ordinal,
        name=f"Phí dịch vụ nền tảng Sariko - đơn hàng {order['id']}",
        property=1,
        quantity=Decimal(1),
        price=commission,
        amount_without_discount=commission,
        amount=commission,
        tax=tax_rate_label(order["vat_rate"]),
        tax_amount=vat,
        amount_after_tax=commission + vat,
    )


def _total_amount(products: list[VatProduct]) -> Decimal:
    """totalAmount: Σ line amounts, before tax. No discount, so also totalAmountWithoutDiscount."""
    return sum((p.amount for p in products), Decimal(0))


def _total_tax_amount(products: list[VatProduct]) -> Decimal:
    """totalTaxAmount: Σ line tax amounts.

    Business: Sariko's output VAT on its service fee (the commission), not on the food subtotal,
    which is the seller's revenue. Each line's tax is orders.vat_amount = round(commission_amount
    * vat_rate, 2), snapshotted at order time (apis/orders.py) with that day's admin_tax_config rate;
    we keep that figure (not a recomputed one) so the invoice matches the DB.
    """
    return sum((p.tax_amount for p in products), Decimal(0))


def _total_amount_after_tax(products: list[VatProduct]) -> Decimal:
    """totalAmountAfterTax: totalAmount + totalTaxAmount — what the seller owes for the commission.
    No fees (totalFeeAmount) on Sariko's invoices, so nothing else is added."""
    return _total_amount(products) + _total_tax_amount(products)


def _tax_types(products: list[VatProduct]) -> list[TaxType]:
    """taxTypes: one entry per tax rate used in the lines, with that rate's amount and tax summed."""
    totals = {}  # tax label → [amount, tax amount]
    for p in products:
        rate_totals = totals.setdefault(p.tax, [Decimal(0), Decimal(0)])
        rate_totals[0] += p.amount
        rate_totals[1] += p.tax_amount
    return [TaxType(tax=tax, amount=amount, tax_amount=tax_amount) for tax, (amount, tax_amount) in totals.items()]


def _buyer_id_number(application: dict):
    """buyerIdNumber: the ID number when it is a CCCD."""
    return application["id_number"] if application["id_type"] == "cccd" else None


def _buyer_passport_number(application: dict):
    """buyerPassportNumber: the ID number when it is a passport."""
    return application["id_number"] if application["id_type"] == "passport" else None


def build_commission_invoice(order: dict, request_id: str, tax_code: str, invoice_symbol: str,
                             currency_unit: str, application: dict) -> OriginalVatInvoiceRequest:
    """`order` and `application` must have passed services/invoice_validation — nothing is checked here.
    `application` is the order's seller's approved onboarding application."""
    products = [_commission_line(1, order)]
    total = _total_amount(products)
    legal_name = buyer_legal_name(application)

    invoice = OriginalVatInvoice(
        request_id=request_id,
        invoice_created_date=vn_today(),
        invoice_symbol=invoice_symbol,
        payment_method=PAYMENT_METHOD,
        currency_unit=currency_unit,
        currency_exchange_rate=CURRENCY_EXCHANGE_RATE,
        discount=False,
        is_petrol_invoice=False,
        is_send_mail=False,
        financial_leasing_invoice=False,
        is_seller_gasoline_business=False,
        is_asset_ownership_registration=False,
        has_auction_authority_info=False,
        created_by=CREATED_BY,
        total_amount_without_discount=total,
        total_amount=total,
        total_tax_amount=_total_tax_amount(products),
        total_amount_after_tax=_total_amount_after_tax(products),
        total_payment_in_word=vnd_in_words(_total_amount_after_tax(products)),
        products=products,
        tax_types=_tax_types(products),
        buyer_customer_code=order["seller_id"],  # seller_profiles.id
        buyer_tax_code=application["tax_code"],
        buyer_name=legal_name,
        buyer_full_name=legal_name,  # TODO: registered business name once we collect it
        buyer_address=application["residential_address"],
        buyer_phone_number=application["phone"],
        buyer_email=application["email"],
        buyer_id_number=_buyer_id_number(application),
        buyer_passport_number=_buyer_passport_number(application),
        buyer_bank_name=application["bank_name"],
        buyer_bank_account_number=application["bank_account_number"],
        buyer_nationality_code=NATIONALITY_CODES.get(application["nationality"]),
        buyer_nationality=application["nationality"],
    )
    return OriginalVatInvoiceRequest(tax_code=tax_code, invoice=invoice, auto_release=False, auto_sign=False)
