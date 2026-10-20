"""TC-13 (spec docs/dev/vnpay-doc-align B5): the old refund gateway of this backend
(/admin/refunds, X-Api-Key) is gone; the admin app refunds through its own backend.

Run from tests/backend:  pytest integration/test_old_refund_gateway_removed.py
"""
import importlib.util

from fastapi.testclient import TestClient


def test_tc13_old_refund_gateway_is_gone(monkeypatch, tmp_path):
    assert importlib.util.find_spec("apis.admin_refunds") is None
    monkeypatch.chdir(tmp_path)   # main makes ./logs on import; tests are read-only in CI
    import main
    client = TestClient(main.app)
    assert client.get("/rest/v1/admin/refunds", headers={"X-Api-Key": "x"}).status_code == 404
    assert client.post("/rest/v1/admin/refunds/some-id/process", headers={"X-Api-Key": "x"}).status_code == 404
