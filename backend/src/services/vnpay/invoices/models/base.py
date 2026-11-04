"""Base for viiAPI request models: camelCase wire format, amounts, tax rates, dates."""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Amount = Decimal
# Appendix 2 — accepted tax rates. "KHAC" alone is allowed (Article 11, Circular 103/2014).
TaxRate = Annotated[str, Field(pattern=r"^(0%|5%|8%|10%|KCT|KKKNT|KHAC(:\d{1,2}(\.\d{1,2})?%)?)$")]
IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]  # yyyy-MM-dd


class CamelModel(BaseModel):
    # snake_case in Python, camelCase on the wire. extra="forbid" so a misspelt field fails here
    # instead of being dropped silently.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    def to_wire(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)
