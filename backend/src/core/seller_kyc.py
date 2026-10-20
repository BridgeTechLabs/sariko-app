"""Seller identity checks shared by /join and the in-app profile form
(spec docs/dev/seller-profile-completion §2b). Pure functions, no DB."""
import re
import unicodedata
from datetime import date

CCCD_RE = re.compile(r"^\d{12}$")            # số định danh cá nhân
BANK_ACCOUNT_RE = re.compile(r"^\d{6,20}$")


def squash(text: str) -> str:
    return " ".join((text or "").split())


def _plain(text: str) -> str:
    """'Nguyễn Văn Ân' -> 'nguyen van an': bank holder names are written without accents."""
    text = squash(text).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").casefold()


def same_name(typed: str, first: str, last: str, ignore_accents: bool = False) -> bool:
    """typed == "first last" or "last first" (spaces squashed, case ignored)."""
    norm = _plain if ignore_accents else (lambda s: squash(s).casefold())
    return norm(typed) in (f"{norm(first)} {norm(last)}", f"{norm(last)} {norm(first)}")


def bank_holder_matches(holder: str, first: str, last: str) -> bool:
    """Luật TMĐT 122/2025 Đ21.2.b: the payout account is in the seller's own name (Q12)."""
    return same_name(holder, first, last, ignore_accents=True)


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
