import logging

from fastapi import APIRouter

from core.sariko_cache import cache
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_promo_banners import DAOPromoBanners

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_KEY = "promo_banners_active"
CACHE_SECONDS = 60   # an admin change reaches the home page within a minute (ADR 0001)


@router.get("/promo-banners")
def get_promo_banners():
    """Public. The banners of the buyer home page, top and footer, each in the admin's order and capped at
    promo_banner_max. A failed read shows no carousel and is not cached, so the next request tries again."""
    lists = cache.get(CACHE_KEY)
    if lists is None:
        try:
            rows = DAOPromoBanners().read_active()
            limit = DAOAdminConfig().get_positive_int("promo_banner_max", 10)
        except Exception as e:
            logger.error(f"[PromoBanners] read failed: {e}")
            return {"success": True, "banners": [], "footer_banners": []}
        pick = lambda placement: [{k: r[k] for k in ("id", "image_url", "link_url", "alt")}
                                  for r in rows if r["placement"] == placement][:limit]
        lists = {"banners": pick("top"), "footer_banners": pick("footer")}
        cache.put(CACHE_KEY, lists, CACHE_SECONDS)
    return {"success": True, **lists}
