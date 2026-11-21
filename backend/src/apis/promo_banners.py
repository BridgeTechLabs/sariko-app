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
    """Public. The banners of the buyer home carousel, in the admin's order. A failed read shows no carousel
    and is not cached, so the next request tries again."""
    banners = cache.get(CACHE_KEY)
    if banners is None:
        try:
            banners = DAOPromoBanners().read_active(DAOAdminConfig().get_positive_int("promo_banner_max", 10))
        except Exception as e:
            logger.error(f"[PromoBanners] read failed: {e}")
            return {"success": True, "banners": []}
        cache.put(CACHE_KEY, banners, CACHE_SECONDS)
    return {"success": True, "banners": banners}
