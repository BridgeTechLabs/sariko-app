"""T209 (seller-menu đợt 4A H1): the one Supabase client FastAPI's threads share talks HTTP/1.1. httpcore's sync HTTP/2
connection broke when threads shared it (StreamIDTooLowError, Supabase PROTOCOL_ERROR, then LocalProtocolError / Broken
pipe on every request on it: 7 x 500 in 1.500 /cart/add on DEV). The parallel check against DEV is
docs/dev/20261112-seller-menu/h1-parallel.py (TC4-32, hub). No network here: the client is only built."""
from clients.supabase import SupabaseService, _RetryOnDisconnectTransport


def test_shared_clients_are_http1_with_the_retry(monkeypatch):   # PostgREST and Storage
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_API_KEY", "x" * 40)
    client = SupabaseService().client
    for transport in (client.postgrest.session._transport, client.storage.session._transport):
        assert isinstance(transport, _RetryOnDisconnectTransport)
        assert transport._pool._http2 is False and transport._pool._http1 is True
