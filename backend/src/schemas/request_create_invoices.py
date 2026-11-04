from pydantic import BaseModel


class RequestCreateInvoices(BaseModel):
    order_ids: list[str]
