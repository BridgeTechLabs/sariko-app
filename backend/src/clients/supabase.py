import os
import logging
from typing import Optional
from fastapi import FastAPI
import httpx
from httpx import HTTPTransport
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class _RetryOnDisconnectTransport(HTTPTransport):
    """Retry once when an idle pooled connection is closed by the server.

    Why: PostgREST/CloudFront may close idle keep-alive connections; httpx hands
    out the stale connection and the next request fails with RemoteProtocolError
    ("Server disconnected"). A single retry lets httpcore evict the dead
    connection and open a fresh one.
    """

    def handle_request(self, request):
        try:
            return super().handle_request(request)
        except httpx.RemoteProtocolError as e:
            logger.warning(f"Supabase stale connection, retrying once: {e}")
            return super().handle_request(request)


class SupabaseService:
    def __init__(self):

        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_API_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")

        self.client: Client = create_client(supabase_url, supabase_key)
        # HTTP/1.1, not HTTP/2 (T209): one client serves FastAPI's whole threadpool, and httpcore's sync HTTP/2
        # connection is not safe for threads sharing it: two threads send their stream headers out of order
        # (StreamIDTooLowError), Supabase closes the connection with PROTOCOL_ERROR and every request on it fails
        # (LocalProtocolError, Broken pipe). HTTP/1.1 gives each request its own pooled connection. Storage (image
        # uploads, signed URLs) is the other shared client the backend uses; auth / functions are never called here.
        self.client.postgrest.session._transport = _RetryOnDisconnectTransport(http2=False)
        self.client.storage.session._transport = _RetryOnDisconnectTransport(http2=False)
        
        
_service: Optional[SupabaseService] = None
def get_supabase_service() -> SupabaseService:
    global _service
    if _service is None:
        _service = SupabaseService()
    return _service

def get_supabase_client() -> Client:
    return get_supabase_service().client