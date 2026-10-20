import ipaddress


def _ip(value: str):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def client_ip(request) -> str:
    """The caller's real IP. The backend sits behind nginx (same host / docker network,
    port not public), which sets X-Real-IP = $remote_addr and appends it to X-Forwarded-For;
    the API is not behind Cloudflare. Those headers are trusted only when the TCP peer is
    that proxy (a private or loopback address), so a direct caller can't fake its IP."""
    peer = request.client.host if request.client else ""
    peer_ip = _ip(peer)
    if peer_ip is not None and peer_ip.is_private:   # is_private covers loopback
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")
        for candidate in (request.headers.get("x-real-ip"), forwarded[-1]):
            if _ip(candidate) is not None:
                return candidate.strip()
    return peer if peer_ip is not None else "127.0.0.1"
