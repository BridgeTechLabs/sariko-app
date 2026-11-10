"""Design mistakes that keep coming back (T172, docs/dev/20261110-refund-state QĐ E), like test_no_float_money.py:
existing cases are frozen per file in a BASELINE that may only shrink; a file going over its count, or a new
file with one, fails.

- [0] of a one-to-many list in order data (refunds, deliveries, payments, ...): the first row is not "the" row;
  ask the backend for the one value you need (e.g. refund_state).
- an enum printed as it is: {{ x.payment_status }}, value: x.status, map[x.status] || x.status. Show text.
- 'duplicate_payment' outside migrations: which refund counts is decided once, in refund_state() (SQL).

Scans backend/src (/www in CI) and the V1 frontend (frontend/src, not v2/). In CI the pipeline mounts
frontend/src read-only at /frontend/src, the same place relative to /tests as in the repo.
Run from tests/backend:  pytest unit/test_no_risky_reads.py
"""
import re
from pathlib import Path

import utils.pricing

BACKEND = Path(utils.pricing.__file__).resolve().parent.parent
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"

FIRST_ROW = re.compile(r"\b(refunds|deliveries|payments|order_items|review_stores|complaints)\b[\"']?\]?\s*(\?\.)?\[0\]")
RAW_ENUM = re.compile(r"\{\{[^}]*\.(payment_status|status|reason)\s*\}\}"
                      r"|\bvalue:\s*[\w.?]+\.(payment_status|status|reason)\b"
                      r"|\]\s*\|\|\s*[\w.?]+\.(status|payment_status|reason)\b")
DUPLICATE = re.compile(r"duplicate_payment")

# The one place allowed to name duplicate_payment: the IPN that writes those refunds.
DUPLICATE_ALLOWED = {"apis/payments.py"}

# Frozen per file; may only go down. TODO (T172): each line left here is a known case to fix later.
BASELINE = {
    "first row": {"frontend/utils/deliveryBadge.js": 1},
    "raw enum": {
        "frontend/components/order-history/OrderCard.vue": 1,           # unknown status shown as is
        "frontend/components/seller-orders/SellerOrdersList.vue": 1,    # unknown status as an i18n key
        "frontend/components/seller-me/SellerMeEarnings.vue": 1,        # maps payout status, then $t: harmless
    },
    "duplicate_payment": {"backend/services/zalo.py": 1},               # the Zalo label of each refund reason
}


def sources():
    """(label, path) of every scanned file."""
    for path in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" not in path.parts and "sql" not in path.relative_to(BACKEND).parts[:1]:
            yield "backend/" + path.relative_to(BACKEND).as_posix(), path
    for path in sorted(FRONTEND.rglob("*")):
        rel = path.relative_to(FRONTEND).as_posix()
        if path.suffix in (".vue", ".js") and "/v2/" not in f"/{rel}" and not rel.startswith("i18n/"):
            yield "frontend/" + rel, path


def found(pattern, allowed=()):
    hits = {}
    for label, path in sources():
        if label.split("/", 1)[1] in allowed:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.setdefault(label, []).append(f"{label}:{n}: {line.strip()}")
    return hits


def over_baseline(name, hits):
    return [line for label, lines in hits.items() if len(lines) > BASELINE[name].get(label, 0) for line in lines]


def test_no_new_first_row_reads():
    over = over_baseline("first row", found(FIRST_ROW))
    assert not over, "[0] of a one-to-many list: ask the backend for the one value instead:\n" + "\n".join(over)


def test_no_new_raw_enums_on_screen():
    over = over_baseline("raw enum", found(RAW_ENUM))
    assert not over, "an enum shown as it is: map it to text (i18n):\n" + "\n".join(over)


def test_duplicate_payment_named_in_one_place():
    over = over_baseline("duplicate_payment", found(DUPLICATE, DUPLICATE_ALLOWED))
    assert not over, "duplicate_payment outside apis/payments.py: use refund_state:\n" + "\n".join(over)


def test_baseline_only_shrinks():
    # A fixed case must leave the baseline too, so it can't come back unnoticed.
    for name, pattern, allowed in (("first row", FIRST_ROW, ()), ("raw enum", RAW_ENUM, ()),
                                   ("duplicate_payment", DUPLICATE, DUPLICATE_ALLOWED)):
        hits = found(pattern, allowed)
        stale = {label: count for label, count in BASELINE[name].items() if len(hits.get(label, [])) < count}
        assert not stale, f"{name}: lower these in BASELINE: {stale}"


def test_scan_finds_both_sources():
    # Guards against a wrong folder (or a CI without the frontend mount) passing on nothing.
    labels = [label for label, _ in sources()]
    assert sum(label.startswith("backend/") for label in labels) > 50
    assert sum(label.startswith("frontend/") for label in labels) > 50, f"no frontend at {FRONTEND}"
