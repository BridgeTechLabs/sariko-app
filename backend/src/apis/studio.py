"""Endpoints for the AI Studio server (post.sariko.store, docs/dev/20261123-studio-integration, ADR 0005). It sends
header X-Studio-Key = STUDIO_API_KEY, a key of its own, not the Admin Gateway's (least privilege). The key unset or
empty turns them off (503): an empty key never matches. Not in the public /docs."""
import hmac
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from dao.dao_orders import DAOOrders
from dao.dao_seller_profiles import DAOSellerProfiles


def verify_studio_key(x_studio_key: str = Header(default="")):
    key = os.getenv("STUDIO_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Studio API is off")
    if not hmac.compare_digest(x_studio_key.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="Invalid Studio key")


router = APIRouter(prefix="/studio", include_in_schema=False)


@router.get("/ref-stats", dependencies=[Depends(verify_studio_key)])
def ref_stats(slug: str, days: int = Query(default=30, ge=1, le=90)):
    """QĐ-2: per post (ref) of a store, how many orders it brought and their dishes' total. Counts only, no buyer data."""
    seller = DAOSellerProfiles().read_seller_by_slug_name(slug)
    if not seller:
        raise HTTPException(status_code=404, detail="Store not found")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stats = defaultdict(lambda: {"orders": 0, "items_total": Decimal(0)})
    for order in DAOOrders().read_ref_orders(seller["id"], since):
        row = stats[(order["ref_code"], order["ref_source"])]
        row["orders"] += 1
        row["items_total"] += Decimal(str(order["subtotal"]))
    refs = [{"ref": ref, "source": source, "orders": row["orders"], "items_total": int(row["items_total"])}
            for (ref, source), row in stats.items()]
    return {"success": True, "slug": slug, "days": days, "refs": refs}
