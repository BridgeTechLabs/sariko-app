"""
Checks before a commission e-invoice is created.

Every check raises ValueError, so a bad order or buyer field stops the invoice before anything is
written or sent to VNPAY. Nothing is cut or dropped silently: a cut ID, account number or name
would be wrong on a legal document. Length limits are viiAPI's (OriginalVatInvoice).
"""
from services.vnpay.invoices.invoice_builder import buyer_legal_name


class InvoiceValidationService:

    def validate_orders(self, order_ids: list[str], orders: list[dict]) -> list[dict]:
        """`orders` as read from the DB; returns them in the caller's order (the invoice line order)."""
        order_by_id = {order["id"]: order for order in orders}

        not_found = [order_id for order_id in order_ids if order_id not in order_by_id]
        if not_found:
            raise ValueError(f"Orders not found: {not_found}")

        not_paid = [order_id for order_id in order_ids if order_by_id[order_id]["payment_status"] != "paid"]
        if not_paid:
            raise ValueError(f"Orders not paid: {not_paid}")

        # Nothing to invoice on an order Sariko took no commission on (e.g. founding tier, 0%).
        no_commission = [order_id for order_id in order_ids if not order_by_id[order_id]["commission_amount"]]
        if no_commission:
            raise ValueError(f"Orders without commission: {no_commission}")

        seller_ids = {order["seller_id"] for order in orders}
        if len(seller_ids) > 1:
            raise ValueError(f"Orders belong to more than one seller: {sorted(seller_ids)}")

        return [order_by_id[order_id] for order_id in order_ids]

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
