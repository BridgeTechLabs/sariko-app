"""Seller identity checks shared by /join and the in-app profile form
(spec docs/dev/seller-profile-completion §2b). Pure functions, no DB."""
import re
import unicodedata
from datetime import date

CCCD_RE = re.compile(r"^\d{12}$")            # số định danh cá nhân
BANK_ACCOUNT_RE = re.compile(r"^\d{6,20}$")
PUNCT = str.maketrans("’ʼ‘–—", "'''--")   # phone keyboards type curly quotes / long dashes


def squash(text: str) -> str:
    return " ".join((text or "").split())


def _plain(text: str) -> str:
    """'Nguyễn Văn Ân' -> 'nguyen van an': bank holder names are written without accents."""
    text = squash(text).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").casefold()


def name_matches(typed: str, full_name: str, ignore_accents: bool = False) -> bool:
    """Same words as the full name, any order, each as many times; case, - ' . ignored (accents too
    for a bank holder). "Nguyễn Văn Ân" matches "AN VAN NGUYEN" but not "NGUYEN AN" (seller-full-name N2)."""
    def words(text):
        # "Anne-Marie O'Brien Jr." -> anne marie obrien jr: banks drop the punctuation
        text = (text or "").translate(PUNCT).replace("-", " ").replace("'", "").replace(".", "")
        return sorted((_plain(text) if ignore_accents else unicodedata.normalize("NFC", squash(text)).casefold()).split())

    return bool(words(full_name)) and words(typed) == words(full_name)


def bank_holder_matches(holder: str, full_name: str) -> bool:
    """Luật TMĐT 122/2025 Đ21.2.b: the payout account is in the seller's own name (Q12)."""
    return name_matches(holder, full_name, ignore_accents=True)


def clean_full_name(text: str):
    """NFC, spaces squashed; None unless it is letters, spaces and - ' . only (one word is fine)."""
    name = unicodedata.normalize("NFC", squash(text)).translate(PUNCT)
    ok = all(c.isalpha() or unicodedata.category(c).startswith("M") or c in " -'." for c in name)
    return name if ok and any(c.isalpha() for c in name) else None


def age(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    days = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, days))


def id_error(id_type: str, id_number: str, expiry: date, today: date, min_validity_months: int):
    """Error code for the ID document, or None. cccd = 12-digit personal ID number;
    a passport must stay valid min_validity_months from today (NĐ 248/2026 Đ18.1.b)."""
    if id_type not in ("passport", "cccd"):
        return "invalid_id_type"
    if id_type == "cccd" and not CCCD_RE.match(squash(id_number)):
        return "invalid_id_number"
    if not squash(id_number):
        return "invalid_id_number"
    if expiry is None:
        return "id_expiry_required"
    if expiry <= today:
        return "id_expired"
    if id_type == "passport" and expiry < _add_months(today, min_validity_months):
        return "id_expiring"
    return None


def valid_bank_account(number: str) -> bool:
    return bool(BANK_ACCOUNT_RE.match(squash(number).replace(" ", "")))


def mask(value) -> str:
    """Last 4 characters only, for showing an ID / account number back to its owner."""
    value = squash(str(value or ""))
    return f"•••• {value[-4:]}" if value else ""
