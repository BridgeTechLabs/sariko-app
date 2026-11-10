"""T177 (docs/dev/20261110-delivery-failed) TC-A48a / A13a: the failed-delivery texts. No counts written into a
sentence (the attempts are a setting), and the buyer reads buyer keys, not the seller's ("no rider in your area").
Reads the V1 frontend at the same place test_no_risky_reads.py does (CI mounts frontend/src at /frontend/src)."""
import json
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"
LOCALES = ("en-PH", "vi")


@pytest.fixture(scope="module", params=LOCALES)
def messages(request):
    return json.loads((FRONTEND / "i18n" / "locales" / f"{request.param}.json").read_text(encoding="utf-8"))


def test_trip_errors_carry_no_count(messages):
    errors = {k: v for k, v in messages["seller_order_detail"].items() if re.fullmatch(r"delivery_\w+_error", k)}
    assert errors and not [k for k, v in errors.items() if re.search(r"\d", v)], errors


def test_buyer_has_its_own_failed_delivery_texts(messages):
    buyer = messages["order_detail"]
    for key in ("reason_no_driver", "reason_delivery_failed", "status_title_delivery_failed", "status_subtext_delivery_failed"):
        assert buyer.get(key), key
    assert not re.search(r"your area|khu vực|Finding a Driver|tìm tài xế", " ".join(
        buyer[k] for k in ("reason_no_driver", "status_title_delivery_failed", "status_subtext_delivery_failed")), re.I)
    assert messages["delivery_tracker"].get("status_LOST")


def test_buyer_reasons_use_buyer_keys():
    header = (FRONTEND / "components" / "order-details" / "OrderStatusHeader.vue").read_text(encoding="utf-8")
    keys = re.findall(r"^\s*'[^']+':\s*'([\w.]+)'", header.split("SYSTEM_REASON_KEYS", 1)[1].split("}", 1)[0], re.M)
    assert keys and all(k.startswith("order_detail.") for k in keys), keys
    assert "'Delivery failed':" in header   # backend apis/orders.py DELIVERY_FAILED_REASON, translated
