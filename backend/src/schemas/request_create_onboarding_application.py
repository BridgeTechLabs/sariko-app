from datetime import date, time
from typing import List, Optional
from pydantic import BaseModel, Field, StrictInt


class OnboardingMenuItem(BaseModel):
    key: str = Field(min_length=1, max_length=40)  # client-made id, links the dish to its photo
    category: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    price: StrictInt  # whole VND; a fractional or string price is a 422
    unit_label: Optional[str] = Field(default=None, max_length=30)
    preorder_day: int = 0


class RequestCreateOnboardingApplication(BaseModel):
    first_name: str = Field(min_length=1, max_length=300)
    last_name: str = Field(min_length=1, max_length=300)
    date_of_birth: date
    nationality: str = Field(min_length=1, max_length=300)
    id_type: str
    id_number: str = Field(min_length=1, max_length=300)
    email: str = Field(max_length=300)
    phone: str = Field(max_length=300)
    residential_address: str = Field(min_length=1, max_length=300)
    tax_code: Optional[str] = Field(default=None, max_length=300)
    tax_resident: Optional[bool] = None

    store_name: str = Field(min_length=1, max_length=300)
    store_description: Optional[str] = Field(default=None, max_length=1000)
    pickup_address: str = Field(min_length=1, max_length=300)
    maps_link: Optional[str] = Field(default=None, max_length=300)
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    menu: List[OnboardingMenuItem]

    tier: str
    founding_invited: bool = False

    bank_name: str = Field(min_length=1, max_length=300)
    bank_account_number: str = Field(min_length=1, max_length=300)
    bank_account_holder: str = Field(min_length=1, max_length=300)

    agreed: bool
    agreement_version: int  # admin_settings.seller_agreement_version, e.g. 20261016
    signature_name: str = Field(min_length=1, max_length=300)
    turnstile_token: str
