from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

# Every group optional: the form sends only what the seller still has to fill in.
# Fields are loose on purpose; the API checks them and answers 400 with a code (same codes as /join).


class ProfileIdentity(BaseModel):
    full_name: str = Field(default="", max_length=300)
    first_name: str = Field(default="", max_length=300)  # older clients; full_name wins when both are sent
    last_name: str = Field(default="", max_length=300)
    date_of_birth: Optional[date] = None
    nationality: str = Field(default="", max_length=300)
    id_type: str = ""                                            # cccd | passport
    id_number: Optional[str] = Field(default=None, max_length=300)  # empty = keep the stored one
    id_expiry_date: Optional[date] = None
    residential_address: str = Field(default="", max_length=300)
    email: Optional[str] = Field(default=None, max_length=300)   # contact email; default = login email


class ProfileTax(BaseModel):
    tax_resident: Optional[bool] = None
    tax_code: Optional[str] = Field(default=None, max_length=300)


class ProfileBank(BaseModel):
    bank_name: str = Field(default="", max_length=300)
    bank_account_number: Optional[str] = Field(default=None, max_length=300)  # empty = keep the stored one
    bank_account_holder: str = Field(default="", max_length=300)


class ProfilePickupAddress(BaseModel):
    address: str = Field(default="", max_length=300)
    lat: Optional[float] = None
    lon: Optional[float] = None


class ProfileAgreement(BaseModel):
    agreed: bool = False
    personal_data_consent: bool = False
    agreement_version: Optional[int] = None
    signature_name: str = Field(default="", max_length=300)


class RequestSellerProfileCompletion(BaseModel):
    identity: Optional[ProfileIdentity] = None
    tax: Optional[ProfileTax] = None
    bank: Optional[ProfileBank] = None
    phone: Optional[str] = Field(default=None, max_length=300)
    full_name: Optional[str] = Field(default=None, max_length=300)  # name fix when only the bank holder mismatches
    pickup_address: Optional[ProfilePickupAddress] = None
    agreement: Optional[ProfileAgreement] = None
