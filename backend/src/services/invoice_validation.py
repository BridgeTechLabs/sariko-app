"""
Checks before a commission e-invoice is created.

Every check raises ValueError, so a bad order or buyer field stops the invoice before anything is
written or sent to VNPAY. Nothing is cut or dropped silently: a cut ID, account number or name
would be wrong on a legal document. Length limits are viiAPI's (OriginalVatInvoice).
"""
from services.vnpay.invoices.invoice_builder import buyer_legal_name


class InvoiceValidationService:

    def validate_order(self, order_id: str, order: dict | None) -> dict:
        """`order` as read from the DB (None when it does not exist); returns it."""
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order["payment_status"] != "paid":
            raise ValueError(f"Order {order_id} is not paid")
        # Nothing to invoice on an order Sariko took no commission on (e.g. founding tier, 0%).
        if not order["commission_amount"]:
            raise ValueError(f"Order {order_id} has no commission")
        return order

    def validate_buyer(self, seller_id: str, application: dict | None) -> None:
        """`application` is the seller's latest approved onboarding application (DAOOnboarding.get_seller_invoice_info).
        Lists every problem at once so the admin can fix them in one go."""
        if not application:
            raise ValueError(f"Seller {seller_id} has no approved onboarding application")

        problems = []
        if not application["tax_code"]:
            problems.append("buyerTaxCode is empty")
        problems += [f"{field} is longer than {limit} characters"
                     for field, value, limit in self._buyer_fields(application) if value and len(value) > limit]
        if problems:
            raise ValueError(f"Seller {seller_id} cannot be invoiced: {'; '.join(problems)}")

    def _buyer_fields(self, application: dict) -> list[tuple[str, str, int]]:
        """(viiAPI field, value, max length) for every buyer field taken from the application."""
        legal_name = buyer_legal_name(application)
        id_field, id_limit = ("buyerIdNumber", 12) if application["id_type"] == "cccd" else ("buyerPassportNumber", 20)
        return [
            ("buyerTaxCode", application["tax_code"], 14),
            ("buyerName", legal_name, 100),
            ("buyerFullName", legal_name, 400),
            ("buyerAddress", application["residential_address"], 400),
            ("buyerPhoneNumber", application["phone"], 20),
            ("buyerEmail", application["email"], 50),
            (id_field, application["id_number"], id_limit),
            ("buyerBankName", application["bank_name"], 400),
            ("buyerBankAccountNumber", application["bank_account_number"], 30),
            ("buyerNationality", application["nationality"], 50),
        ]
