"""Unit tests for the VNPAY Invoice access token (services/vnpay/invoices/auth.py).

Why this matters: every viiAPI call needs this token. A broken cache either hammers
the token endpoint on every call or keeps sending an expired token.
"""
import pytest
import requests

from services.vnpay.invoices import VnpayInvoiceConfig, VnpayInvoiceError, TokenManager


class FakeResponse:
    def __init__(self, body=None, status_code=200, text=None):
        self._body = body
        self.status_code = status_code
        self.text = text if text is not None else str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _ok(token="tok-1", expires_in=3600):
    return FakeResponse({"code": "00", "message": "Success", "traceId": "tr-1",
                         "data": {"accessToken": token, "expiresIn": expires_in}})


@pytest.fixture
def config():
    return VnpayInvoiceConfig(base_url="https://invoice-api.test", client_id="cid", client_secret="csecret")


@pytest.fixture
def calls(monkeypatch):
    """Queue responses for requests.post and record each call."""
    state = {"responses": [], "calls": []}

    def fake_post(url, json=None, timeout=None):
        state["calls"].append({"url": url, "json": json, "timeout": timeout})
        return state["responses"].pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    return state


def test_fetches_token_with_client_credentials(config, calls):
    calls["responses"] = [_ok()]
    assert TokenManager(config).get_token() == "tok-1"
    assert calls["calls"] == [{
        "url": "https://invoice-api.test/user/client/token",
        "json": {"clientId": "cid", "clientSecret": "csecret"},
        "timeout": 20,
    }]


def test_token_is_cached(config, calls):
    calls["responses"] = [_ok()]
    tm = TokenManager(config, clock=FakeClock())
    tm.get_token()
    tm.get_token()
    assert len(calls["calls"]) == 1


def test_fetches_new_token_shortly_before_expiry(config, calls):
    clock = FakeClock()
    calls["responses"] = [_ok("tok-1", 3600), _ok("tok-2", 3600)]
    tm = TokenManager(config, clock=clock)
    assert tm.get_token() == "tok-1"

    clock.now += 3600 - TokenManager.REFRESH_MARGIN - 1
    assert tm.get_token() == "tok-1"

    clock.now += 1
    assert tm.get_token() == "tok-2"


def test_short_lifetime_still_caches(config, calls):
    """expiresIn below the margin must not refetch on every call."""
    clock = FakeClock()
    calls["responses"] = [_ok("tok-1", 30)]
    tm = TokenManager(config, clock=clock)
    tm.get_token()
    clock.now += 10
    assert tm.get_token() == "tok-1"
    assert len(calls["calls"]) == 1


def test_invalidate_forces_refetch(config, calls):
    calls["responses"] = [_ok("tok-1"), _ok("tok-2")]
    tm = TokenManager(config, clock=FakeClock())
    tm.get_token()
    tm.invalidate()
    assert tm.get_token() == "tok-2"


def test_error_code_raises_with_trace_id(config, calls):
    calls["responses"] = [FakeResponse({"code": "11", "message": "Invalid clientId", "traceId": "tr-err", "data": None},
                                       status_code=400)]
    with pytest.raises(VnpayInvoiceError) as exc:
        TokenManager(config).get_token()
    assert exc.value.code == "11"
    assert exc.value.trace_id == "tr-err"
    assert exc.value.http_status == 400


def test_missing_access_token_raises(config, calls):
    calls["responses"] = [FakeResponse({"code": "00", "message": "Success", "traceId": "tr", "data": {}})]
    with pytest.raises(VnpayInvoiceError):
        TokenManager(config).get_token()


def test_non_json_response_raises(config, calls):
    calls["responses"] = [FakeResponse(None, status_code=502, text="<html>Bad Gateway</html>")]
    with pytest.raises(VnpayInvoiceError) as exc:
        TokenManager(config).get_token()
    assert exc.value.http_status == 502


def test_failed_fetch_does_not_cache(config, calls):
    calls["responses"] = [FakeResponse({"code": "-1", "message": "Unknown", "traceId": "t"}, status_code=500), _ok()]
    tm = TokenManager(config)
    with pytest.raises(VnpayInvoiceError):
        tm.get_token()
    assert tm.get_token() == "tok-1"


def test_config_from_env_requires_credentials(monkeypatch):
    monkeypatch.setenv("VNPAY_INVOICE_URL", "https://invoice-api.test/")
    monkeypatch.setenv("VNPAY_INVOICE_CLIENT_ID", "cid")
    monkeypatch.delenv("VNPAY_INVOICE_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        VnpayInvoiceConfig.from_env()

    monkeypatch.setenv("VNPAY_INVOICE_CLIENT_SECRET", "csecret")
    assert VnpayInvoiceConfig.from_env().base_url == "https://invoice-api.test"
