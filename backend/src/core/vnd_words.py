"""
VND amount in Vietnamese words, as written on an invoice (totalPaymentInWord).

31900 → "Ba mươi mốt nghìn chín trăm đồng". Read in groups of 3 digits; a group that is not the
leading one always reads its hundred ("không trăm"), so 1015 is "một nghìn không trăm mười lăm".
num2words gets that case wrong ("một nghìn lẻ mười lăm"), hence this module.
VND has no subunit in use, so an amount with a fractional part is rejected rather than guessed.
"""
from decimal import Decimal

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
# Unit digit after "mươi" (20-99) and after "mười" (10-19); anything else reads as DIGITS.
AFTER_MUOI = {0: "", 1: "mốt", 4: "tư", 5: "lăm"}
AFTER_MUOI_10 = {0: "", 5: "lăm"}


def _read_group(n: int, full: bool) -> str:
    """One group of 3 digits (1-999). `full` = not the leading group, so a 0 hundred reads "không trăm"."""
    hundreds, tens, units = n // 100, n // 10 % 10, n % 10
    words = [f"{DIGITS[hundreds]} trăm"] if hundreds or full else []
    if tens == 0:
        if units:
            words.append(f"linh {DIGITS[units]}" if words else DIGITS[units])
    elif tens == 1:
        words.append("mười")
        words.append(AFTER_MUOI_10.get(units, DIGITS[units]))
    else:
        words.append(f"{DIGITS[tens]} mươi")
        words.append(AFTER_MUOI.get(units, DIGITS[units]))
    return " ".join(w for w in words if w)


def _scale(index: int) -> str:
    """Group index from the right → its unit: "", nghìn, triệu, tỷ, nghìn tỷ, triệu tỷ, tỷ tỷ, ..."""
    return " ".join(w for w in [["", "nghìn", "triệu"][index % 3]] + ["tỷ"] * (index // 3) if w)


def vnd_in_words(amount) -> str:
    """Raises ValueError for a negative amount or one with a fractional part."""
    value = Decimal(str(amount))
    if value < 0:
        raise ValueError(f"Amount must not be negative: {amount}")
    if value != value.to_integral_value():
        raise ValueError(f"Amount has a fractional part, VND cannot be read in words: {amount}")

    number = int(value)
    if number == 0:
        return "Không đồng"

    groups = []  # least significant first
    while number:
        number, group = divmod(number, 1000)
        groups.append(group)

    parts = []
    for index in range(len(groups) - 1, -1, -1):
        if groups[index]:
            full = index != len(groups) - 1
            parts.append(" ".join(w for w in [_read_group(groups[index], full), _scale(index)] if w))

    text = " ".join(parts)
    return f"{text[0].upper()}{text[1:]} đồng"
