"""T162 AllinGo wallet low alert (docs/dev/20261110-allingo-wallet). AllinGo's HTTP is faked at requests.request
(the real AllingoService builds the call), admin_settings and the clock are faked. No DB, no network."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
import requests

from services import allingo_service, allingo_wallet, job_health, push_service, zalo

BASE = "https://pro.allingo.vn/api/v1"


def reply(status, body=None):
    text = json.dumps(body) if body is not None else ""
    return SimpleNamespace(status_code=status, ok=200 <= status < 300, text=text, json=lambda: json.loads(text))


class World:
    """GET /wallet answers (one per call, the last repeats), admin_settings, the clock and the alerts sent."""

    def __init__(self):
        self.wallet = [reply(200, {"delivery_credit": 2450000, "currency": "VND"})]
        self.settings = {"allingo_wallet_alert_vnd": 500000, "allingo_wallet_alert_repeat_hours": 6}
        self.settings_down = False
        self.now, self.tokens, self.alerts = 1000.0, 0, []

    def balance(self, amount):
        self.wallet = [reply(200, {"delivery_credit": amount, "currency": "VND"})]

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        path = url.replace(BASE, "")
        if path == "/oauth/token":
            self.tokens += 1
            return reply(200, {"access_token": f"tok{self.tokens}", "expires_in": 3600})
        assert (method, path) == ("GET", "/wallet")
        answer = self.wallet.pop(0) if len(self.wallet) > 1 else self.wallet[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def config(self):
        world = self

        class Config:
            def get_positive_ints(self, defaults):
                assert set(defaults) == set(world.settings)
                if world.settings_down:
                    raise Exception("db down")
                return dict(world.settings)
        return Config()


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("ALLINGO_APP_ID", "app_test_x")
    monkeypatch.setenv("ALLINGO_APP_SECRET", "sk_test_x")
    allingo_service.reset_allingo_service()
    w = World()
    monkeypatch.setattr(allingo_service.requests, "request", w.request)
    monkeypatch.setattr(allingo_wallet, "DAOAdminConfig", w.config)
    monkeypatch.setattr(allingo_wallet.time, "monotonic", lambda: w.now)
    monkeypatch.setattr(allingo_wallet, "_settings", dict(allingo_wallet.DEFAULTS))
    monkeypatch.setattr(allingo_wallet, "_alerted_at", None)
    monkeypatch.setattr(push_service, "notify_admins", lambda event, url, **f: w.alerts.append((event, url, f)))
    yield w
    allingo_service.reset_allingo_service()


def test_tc1_balance_at_or_above_threshold_no_alert(world):
    allingo_wallet.check()
    world.balance(500000)   # TC-11: equal to the threshold is not below it
    allingo_wallet.check()
    assert world.alerts == []


def test_tc2_alert_once_then_every_repeat_hours(world):
    world.balance(320000)
    allingo_wallet.check()
    assert world.alerts == [("admin_delivery_wallet_low", "/monitoring", {"balance": "320.000 ₫", "threshold": "500.000 ₫"})]
    world.now += 6 * 3600 - 1
    allingo_wallet.check()
    assert len(world.alerts) == 1
    world.now += 1
    allingo_wallet.check()
    assert len(world.alerts) == 2


def test_tc3_back_above_then_below_alerts_at_once(world):
    world.balance(100000)
    allingo_wallet.check()
    world.balance(900000)
    world.now += 60
    allingo_wallet.check()
    world.balance(100000)
    world.now += 60
    allingo_wallet.check()
    assert len(world.alerts) == 2


@pytest.mark.parametrize("answer", [
    requests.Timeout("read timed out"),   # TC-15: timeout
    reply(429, {"error": {"code": "rate_limited"}}),
    reply(503, {"error": {"code": "unavailable"}}),
    reply(404, {"error": {"code": "wallet_not_found"}}),
])
def test_tc4_tc15_allingo_error_raises_and_keeps_the_state(world, answer):
    world.balance(100000)
    allingo_wallet.check()
    world.now += 7 * 3600
    world.wallet = [answer]
    with pytest.raises(allingo_service.AllingoError):
        allingo_wallet.check()
    assert len(world.alerts) == 1 and allingo_wallet._alerted_at == 1000.0


def test_tc15_expired_token_renewed_once(world):
    world.wallet = [reply(401), reply(200, {"delivery_credit": 100000, "currency": "VND"})]
    allingo_wallet.check()
    assert world.tokens == 2 and len(world.alerts) == 1


@pytest.mark.parametrize("body", [
    {"currency": "VND"},                                   # balance missing
    {"delivery_credit": None, "currency": "VND"},
    {"delivery_credit": "abc", "currency": "VND"},
    {"delivery_credit": "NaN", "currency": "VND"},
    {"delivery_credit": 100000, "currency": "USD"},       # another currency
    {"delivery_credit": 100000},
])
def test_tc10_odd_answer_is_an_error_not_zero(world, body):
    world.wallet = [reply(200, body)]
    with pytest.raises(allingo_service.AllingoError) as e:
        allingo_wallet.check()
    assert e.value.code == "allingo_bad_answer" and world.alerts == []


@pytest.mark.parametrize("raw, expected", [("1500000.00", 1500000), (1500000, 1500000), ("0", 0)])
def test_tc10_balance_in_whole_dong(world, raw, expected):
    world.wallet = [reply(200, {"delivery_credit": raw, "currency": "VND"})]
    assert allingo_service.get_allingo_service().wallet_balance() == expected


@pytest.mark.parametrize("amount, shown", [(0, "0 ₫"), (-50000, "-50.000 ₫")])
def test_tc11_zero_and_negative_balance_alert(world, amount, shown):
    world.balance(amount)
    allingo_wallet.check()
    assert world.alerts[0][2]["balance"] == shown


def test_tc6_new_threshold_read_every_tick(world):
    world.balance(700000)
    allingo_wallet.check()
    world.settings["allingo_wallet_alert_vnd"] = 1000000
    allingo_wallet.check()
    assert world.alerts[0][2] == {"balance": "700.000 ₫", "threshold": "1.000.000 ₫"}


def test_tc17_settings_read_error_keeps_the_last_values(world):
    world.settings["allingo_wallet_alert_vnd"] = 200000
    world.balance(300000)
    allingo_wallet.check()   # reads 200.000 ₫: above, no alert
    world.settings_down = True
    allingo_wallet.check()   # read fails: still 200.000 ₫, not the 500.000 ₫ default
    assert world.alerts == []


def test_tc17_zero_or_negative_setting_uses_the_default():
    from dao.dao_admin_config import DAOAdminConfig
    assert DAOAdminConfig._positive_int("allingo_wallet_alert_vnd", 0, 500000) == 500000
    assert DAOAdminConfig._positive_int("allingo_wallet_alert_repeat_hours", -6, 6) == 6


@pytest.mark.parametrize("app_id, secret, runs", [("", "", False), ("app_x", "", False), ("", "sk_x", False),
                                                  ("app_x", "sk_x", True)])
def test_tc5_tc12_tc13_job_only_with_both_keys(monkeypatch, app_id, secret, runs):
    monkeypatch.setenv("ALLINGO_APP_ID", app_id)
    monkeypatch.setenv("ALLINGO_APP_SECRET", secret)
    started = []

    async def every(job, default_interval, run):
        started.append((job, default_interval, run))
    monkeypatch.setattr(job_health, "every", every)
    asyncio.run(allingo_wallet.run_allingo_wallet())
    assert started == ([("allingo_wallet", 1800, allingo_wallet.check)] if runs else [])


def test_tc15_job_has_a_plain_name():
    assert job_health.NAMES["allingo_wallet"] == "AllinGo wallet check"


def test_tc14_message_in_push_en_vi_and_zalo(monkeypatch):
    sent = []
    monkeypatch.setattr(zalo, "send", lambda kind, text: sent.append((kind, text)))
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", None)
    fields = {"balance": "320.000 ₫", "threshold": "500.000 ₫"}
    push_service.notify_admins("admin_delivery_wallet_low", "/monitoring", **fields)
    assert sent == [("ops", "🪫 AllinGo wallet low: 320.000 ₫ (alert below 500.000 ₫). Top up before trips start failing.\n"
                            "https://admin.sariko.store/monitoring")]
    for lang in ("en", "vi"):
        title, body = push_service._message("admin_delivery_wallet_low", lang, fields)
        assert "320.000 ₫" in body and "500.000 ₫" in body and "{" not in title + body


def test_tc16_wallet_and_booking_share_the_token(world):
    """The job thread and a booking request at once, token almost expired: both work, at most 2 token requests."""
    service = allingo_service.get_allingo_service()
    service._token, service._token_until = "old", allingo_service.time.time() + 60
    errors = []

    def call():
        try:
            service.wallet_balance()
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and 1 <= world.tokens <= 2
