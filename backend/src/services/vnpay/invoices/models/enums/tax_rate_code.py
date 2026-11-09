"""TaxRateCode — accepted VAT rate values, viiAPI appendix 2 (Decision 1510/QĐ-TCT)."""
from enum import StrEnum


class TaxRateCode(StrEnum):
    RATE_0 = "0%"               # 0% rate
    RATE_5 = "5%"               # 5% rate
    RATE_8 = "8%"               # 8% rate
    RATE_10 = "10%"             # 10% rate
    NON_TAX = "KCT"             # Not subject to VAT
    NOT_DECLARED = "KKKNT"      # Not declared / not liable to pay VAT
    # Other rate: "KHAC:AB.CD%" when the rate is known (e.g. KHAC:5.26%, KHAC:7%),
    # plain "KHAC" for taxpayers under Article 11, Circular 103/2014/TT-BTC.
    OTHER = "KHAC"
