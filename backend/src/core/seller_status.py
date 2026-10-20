def with_buyer_status(seller: dict) -> dict:
    """Buyer-facing reads: an active store without pickup coordinates shows as coming_soon,
    since Lalamove can't quote a trip from it (spec seller-profile-completion §3.6). The DB
    status is not touched; it turns active again as soon as the seller saves the address."""
    if seller is not None and seller.get("status") == "active" and (seller.get("lat") is None or seller.get("lon") is None):
        seller["status"] = "coming_soon"
    return seller
