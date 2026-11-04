"""Base for the invoice detail response models."""
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class DetailModel(BaseModel):
    # The doc and the sandbox disagree on some types (invoiceType: doc integer, sandbox "1"),
    # so numbers are accepted for str fields. Unknown fields are ignored, not rejected.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, coerce_numbers_to_str=True)
