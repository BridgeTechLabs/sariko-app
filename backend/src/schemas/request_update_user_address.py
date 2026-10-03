from typing import Optional
from pydantic import BaseModel, Field, model_validator


class RequestUpdateUserAddress(BaseModel):
    address: str = Field(min_length=1)
    receiver_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    phone_number: Optional[str] = Field(default=None, min_length=1)
    label: Optional[str] = None
    lat: float
    lon: float
    note: Optional[str] = None
    street_name: Optional[str] = None
    is_default: Optional[bool] = None

    @model_validator(mode="after")
    def reject_null_required(self):
        # The route dumps with exclude_unset so a client can clear `note` with null;
        # these fields are required on create, so an explicit null must be a 422.
        for field in ("receiver_name", "phone_number", "is_default"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
