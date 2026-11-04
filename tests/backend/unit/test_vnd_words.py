"""core/vnd_words.py — VND amounts in Vietnamese words for totalPaymentInWord.

Why this matters: the amount in words is printed on a legal invoice next to the amount in figures;
a wrong reading (num2words says "một nghìn lẻ mười lăm" for 1015) is a wrong invoice.
"""
from decimal import Decimal

import pytest

from core.vnd_words import vnd_in_words


@pytest.mark.parametrize("amount, words", [
    # units
    (0, "Không đồng"),
    (1, "Một đồng"),
    (4, "Bốn đồng"),
    (5, "Năm đồng"),
    (9, "Chín đồng"),
    # 10-19: "mười", 5 → "lăm", 1 and 4 stay "một" / "bốn"
    (10, "Mười đồng"),
    (11, "Mười một đồng"),
    (14, "Mười bốn đồng"),
    (15, "Mười lăm đồng"),
    (19, "Mười chín đồng"),
    # 20-99: "mươi", 1 → "mốt", 4 → "tư", 5 → "lăm"
    (20, "Hai mươi đồng"),
    (21, "Hai mươi mốt đồng"),
    (24, "Hai mươi tư đồng"),
    (25, "Hai mươi lăm đồng"),
    (99, "Chín mươi chín đồng"),
    # hundreds: tens 0 → "linh"
    (100, "Một trăm đồng"),
    (101, "Một trăm linh một đồng"),
    (105, "Một trăm linh năm đồng"),
    (110, "Một trăm mười đồng"),
    (115, "Một trăm mười lăm đồng"),
    (121, "Một trăm hai mươi mốt đồng"),
    (999, "Chín trăm chín mươi chín đồng"),
    # a non-leading group always reads its hundred ("không trăm") — where num2words is wrong
    (1000, "Một nghìn đồng"),
    (1005, "Một nghìn không trăm linh năm đồng"),
    (1010, "Một nghìn không trăm mười đồng"),
    (1015, "Một nghìn không trăm mười lăm đồng"),
    (2014, "Hai nghìn không trăm mười bốn đồng"),
    (1100, "Một nghìn một trăm đồng"),
    (21000, "Hai mươi mốt nghìn đồng"),
    (31900, "Ba mươi mốt nghìn chín trăm đồng"),
    (32050, "Ba mươi hai nghìn không trăm năm mươi đồng"),
    (100000, "Một trăm nghìn đồng"),
    (105000, "Một trăm linh năm nghìn đồng"),
    # all-zero groups are skipped; the next group still reads "không trăm"
    (1000000, "Một triệu đồng"),
    (1000005, "Một triệu không trăm linh năm đồng"),
    (1001000, "Một triệu không trăm linh một nghìn đồng"),
    (1015000, "Một triệu không trăm mười lăm nghìn đồng"),
    (2500000000, "Hai tỷ năm trăm triệu đồng"),
    (1000000000000, "Một nghìn tỷ đồng"),
    (1000050000000, "Một nghìn tỷ không trăm năm mươi triệu đồng"),
    (2000000000000000, "Hai triệu tỷ đồng"),
])
def test_vnd_in_words(amount, words):
    assert vnd_in_words(amount) == words


@pytest.mark.parametrize("amount", [Decimal("31900"), Decimal("31900.00"), 31900.0, "31900"])
def test_accepts_whole_amounts_in_any_numeric_form(amount):
    assert vnd_in_words(amount) == "Ba mươi mốt nghìn chín trăm đồng"


@pytest.mark.parametrize("amount", [Decimal("2580.11"), 0.5, "100.01"])
def test_fractional_amount_raises(amount):
    with pytest.raises(ValueError, match="fractional part"):
        vnd_in_words(amount)


def test_negative_amount_raises():
    with pytest.raises(ValueError, match="negative"):
        vnd_in_words(-1000)
