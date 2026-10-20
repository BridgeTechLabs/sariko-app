"""Money must not go through float (docs/tracking/loi-lap-lai.txt L7): use Decimal(str(x)).
Scans every .py under backend/src for float( / : float / -> float on a line that also names
money. Existing violations are frozen per file in BASELINE; a file going over its count, or
any new file with one, fails. No DB, no network.

Run from tests/backend:  pytest unit/test_no_float_money.py
"""
import re
from pathlib import Path

import utils.pricing

SRC = Path(utils.pricing.__file__).resolve().parent.parent   # backend/src locally, /www in CI

FLOAT = re.compile(r"float\(|:\s*float\b|->\s*float\b")
MONEY = re.compile(r"price|amount|fee|commission|payout|refund|total|subtotal|vat|vnd|money|cost", re.I)

# Lines per file on 2026-10-20 (TODO T89). Lower the count when T89 fixes one.
BASELINE = {
    "apis/payments.py": 2,
    "apis/sellers.py": 1,
    "dao/dao_admin_config.py": 1,
    "dao/dao_orders.py": 4,
    "dao/dao_payments.py": 1,
    "dao/dao_refunds.py": 1,
    "dao/dao_seller_profiles.py": 1,
    "schemas/request_create_food_item.py": 1,
    "schemas/request_create_variant.py": 1,
    "services/lalamove_service.py": 1,
    "utils/pricing.py": 1,
}


def money_floats():
    """{relative path: [(line number, line)]} of float-for-money lines."""
    found = {}
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(SRC).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FLOAT.search(line) and MONEY.search(line):
                found.setdefault(rel, []).append((n, line.strip()))
    return found


def test_no_new_float_for_money():
    over = []
    for rel, lines in money_floats().items():
        if len(lines) > BASELINE.get(rel, 0):
            over += [f"{rel}:{n}: {line}" for n, line in lines]
    assert not over, (
        "float used for money (use Decimal(str(x)); cast to int only when serializing):\n"
        + "\n".join(over)
    )


def test_scan_finds_the_source():
    # Guards against SRC pointing at the wrong folder and the test passing on nothing.
    assert (SRC / "main.py").is_file() and len(list(SRC.rglob("*.py"))) > 50
