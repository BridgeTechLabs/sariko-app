from dao.dao_base import DAOBase


class DAOPromoBanners(DAOBase):
    """admin_promo_banners: the admin app writes, the buyer home page reads (docs/dev/20261121-promo-banners)."""

    def read_active(self, limit: int) -> list:
        result = (
            self._supabase_client
            .table("admin_promo_banners")
            .select("id, image_url, link_url, alt")
            .eq("is_active", True)
            .order("position")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return result.data or []
