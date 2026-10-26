"""T35 complaints API (docs/dev/complaints/README.md TC-2..TC-6, TC-9, TC-12, Q9). DAO, storage and push faked;
the SQL side (code, hold, status) is checked on DEV with docs/dev/complaints/tc_dev_check.sql."""
import base64
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from apis import complaints
from core.auth import verify_token
from dao.dao_admin_config import DAOAdminConfig
from dao.dao_complaints import ComplaintOpenExists

BUYER, SELLER_USER, STRANGER = "buyer-1", "seller-user-1", "stranger-1"


def _jpg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def _ago(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


class FakeDAO:
    def __init__(self):
        self.orders, self.rows = {}, {}

    def read_order(self, order_id):
        return self.orders.get(order_id)

    def create(self, order_id, user_id, sender_role, category, description):
        if any(r["order_id"] == order_id and r["user_id"] == user_id and r["status"] != "resolved" for r in self.rows.values()):
            raise ComplaintOpenExists()
        n = len(self.rows) + 1
        row = {"id": f"c{n}", "code": f"KN{n:06d}", "order_id": order_id, "user_id": user_id, "sender_role": sender_role,
               "channel": "app", "category": category, "description": description, "image_paths": [], "status": "received",
               "resolution": None, "created_at": _ago(0), "acknowledged_at": None, "resolved_at": None,
               "held_payout": sender_role == "buyer"}
        self.rows[row["id"]] = row
        return row

    def read(self, complaint_id):
        row = self.rows.get(complaint_id)
        return {k: v for k, v in row.items() if k != "held_payout"} if row else None   # PUBLIC_FIELDS

    def set_image_paths(self, complaint_id, paths):
        self.rows[complaint_id]["image_paths"] = paths

    def list_by_user(self, user_id):
        return [r for r in self.rows.values() if r["user_id"] == user_id]

    def list_for_order(self, order_id):
        return [r for r in self.rows.values() if r["order_id"] == order_id]


@pytest.fixture
def env(monkeypatch):
    dao = FakeDAO()
    dao.orders["o1"] = {"id": "o1", "user_id": BUYER, "status": "done", "payment_status": "paid",
                        "status_changed_at": _ago(2), "seller_profiles": {"user_id": SELLER_USER}}
    settings = {"complaint_window_hours": 24, "complaint_max_images": 2, "onboarding_max_file_mb": 5}
    pushed, uploaded = [], []
    monkeypatch.setattr(complaints, "DAOComplaints", lambda: dao)
    monkeypatch.setattr(DAOAdminConfig, "__init__", lambda self: None)
    monkeypatch.setattr(DAOAdminConfig, "get_positive_ints", lambda self, d: {k: settings.get(k, v) for k, v in d.items()})
    monkeypatch.setattr(DAOAdminConfig, "get_positive_int", lambda self, k, d: settings.get(k, d))
    monkeypatch.setattr(complaints.push_service, "notify_seller_complaint", lambda uid, oid: pushed.append((uid, oid)))
    monkeypatch.setattr(complaints.push_service, "notify_admins",
                        lambda event, url, **f: pushed.append((event, url, f)))
    monkeypatch.setattr(complaints, "upload_private", lambda bucket, path, content, ct: uploaded.append((bucket, path, ct)))
    monkeypatch.setattr(complaints, "signed_url", lambda bucket, path, s: f"https://signed/{bucket}/{path}")
    user = {"id": BUYER}
    app = FastAPI()
    app.include_router(complaints.router)
    app.dependency_overrides[verify_token] = lambda: user

    class Env:
        pass
    e = Env()
    e.dao, e.settings, e.pushed, e.uploaded, e.client = dao, settings, pushed, uploaded, TestClient(app)
    e.as_user = lambda uid: user.update(id=uid)
    return e


def post(env, **body):
    return env.client.post("/complaints", json={"order_id": "o1", "category": "damaged", "description": "Cold food", **body})


def test_tc2_buyer_files_with_photo(env):
    res = post(env)
    assert res.status_code == 200, res.text
    c = res.json()["complaint"]
    assert c["code"] == "KN000001" and c["status"] == "received"
    assert env.pushed == [(SELLER_USER, "o1"),                          # TC-12: seller told
                          ("admin_new_complaint", f"/complaints?open={c['id']}",   # admin-push TC-3
                           {"code": "KN000001", "category": "damaged"})]
    res = env.client.post(f"/complaints/{c['id']}/images", json={"image_base64": "data:image/jpeg;base64," + _jpg()})
    assert res.status_code == 200 and res.json()["image_count"] == 1
    assert env.uploaded == [("complaints", f"{c['id']}/1.jpg", "image/jpeg")]   # private bucket


def test_tc3_window_closed(env):
    env.dao.orders["o1"]["status_changed_at"] = _ago(25)
    res = post(env)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "window_closed"
    assert res.json()["detail"]["hours"] == 24 and env.dao.rows == {}


def test_open_order_has_no_window(env):
    env.dao.orders["o1"].update(status="confirmed", status_changed_at=_ago(100))
    assert post(env).status_code == 200


def test_tc4_not_mine_or_unpaid(env):
    env.as_user(STRANGER)
    res = post(env)
    assert res.status_code == 403 and res.json()["detail"]["code"] == "not_your_order"
    env.as_user(BUYER)
    env.dao.orders["o1"]["payment_status"] = "pending"
    res = post(env)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "order_not_paid"
    assert env.dao.rows == {}


def test_tc5_one_open_complaint(env):
    assert post(env).status_code == 200
    res = post(env)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "complaint_open"
    env.dao.rows["c1"]["status"] = "resolved"
    assert post(env).status_code == 200


@pytest.mark.parametrize("body, code", [
    ({"category": "buyer_issue"}, "invalid_category"),         # a seller's type
    ({"description": "   "}, "missing_field"),
    ({"description": "x" * 2001}, "description_too_long"),
])
def test_tc6_fields(env, body, code):
    res = post(env, **body)
    assert res.status_code == 400 and res.json()["detail"]["code"] == code
    assert env.dao.rows == {}


def test_tc6_images(env):
    cid = post(env).json()["complaint"]["id"]
    up = lambda data: env.client.post(f"/complaints/{cid}/images", json={"image_base64": data})
    assert up(base64.b64encode(b"%PDF-1.4 x").decode()).json()["detail"]["code"] == "invalid_file_type"
    assert up(_jpg()).status_code == 200 and up(_jpg()).status_code == 200
    res = up(_jpg())
    assert res.status_code == 400 and res.json()["detail"] == {"code": "too_many_images", "message": "Too many photos", "max": 2}
    env.as_user(SELLER_USER)
    assert up(_jpg()).status_code == 404                     # only the sender adds photos


def test_tc9_seller_files_no_seller_push(env):
    env.as_user(SELLER_USER)
    res = post(env, category="buyer_issue")
    assert res.status_code == 200 and env.dao.rows["c1"]["sender_role"] == "seller"
    # no seller push; admins hear about a seller's complaint too (admin-push Q4a)
    assert env.pushed == [("admin_new_complaint", "/complaints?open=c1", {"code": "KN000001", "category": "buyer_issue"})]


def test_q9_who_sees_what(env):
    cid = post(env).json()["complaint"]["id"]
    env.client.post(f"/complaints/{cid}/images", json={"image_base64": _jpg()})
    env.dao.rows[cid]["admin_note"] = "internal"   # what the DB would hold; PUBLIC_FIELDS never selects it
    for uid in (BUYER, SELLER_USER):
        env.as_user(uid)
        c = env.client.get(f"/complaints/{cid}").json()["complaint"]
        assert c["code"] == "KN000001" and c["images"] == [f"https://signed/complaints/{cid}/1.jpg"]
        assert c["is_mine"] == (uid == BUYER)
    env.as_user(STRANGER)
    assert env.client.get(f"/complaints/{cid}").status_code == 404
    env.as_user(BUYER)
    mine = env.client.get("/complaints/mine").json()["complaints"]
    assert [m["code"] for m in mine] == ["KN000001"] and mine[0]["order_id"] == "o1"


def test_order_detail_flags(env):
    order = env.dao.orders["o1"]
    assert complaints.complaints_for_order(order, BUYER, "buyer") == {"complaints": [], "can_complain": True}
    post(env)
    env.as_user(SELLER_USER)
    post(env, category="other")
    buyer_view = complaints.complaints_for_order(order, BUYER, "buyer")
    assert [c["sender_role"] for c in buyer_view["complaints"]] == ["buyer"] and buyer_view["can_complain"] is False
    seller_view = complaints.complaints_for_order(order, SELLER_USER, "seller")
    assert sorted(c["sender_role"] for c in seller_view["complaints"]) == ["buyer", "seller"]
    assert all("admin_note" not in c for c in seller_view["complaints"])
    order["status_changed_at"] = _ago(30)
    env.dao.rows.clear()
    assert complaints.complaints_for_order(order, BUYER, "buyer")["can_complain"] is False   # window closed


def test_config(env):
    body = env.client.get("/complaints/config").json()
    assert (body["window_hours"], body["max_images"], body["max_length"]) == (24, 2, 2000)
    assert (body["ack_hours"], body["resolve_working_days"]) == (24, 7)
    assert "damaged" in body["categories"]["buyer"] and "buyer_issue" in body["categories"]["seller"]


def test_order_screen_survives_a_complaints_error(env, monkeypatch):
    def boom(order_id):
        raise RuntimeError("relation complaints does not exist")
    monkeypatch.setattr(env.dao, "list_for_order", boom)
    assert complaints.complaints_for_order(env.dao.orders["o1"], BUYER, "buyer") == {"complaints": [], "can_complain": False}


# complaint-email TC-1..TC-3: new complaint → one email to support, in the background, never breaking the API
class FakeSMTP:
    sent, logins, fail = [], [], False

    def __init__(self, host, port, timeout):
        FakeSMTP.host = (host, port, timeout)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        if FakeSMTP.fail:
            raise complaints.email_service.smtplib.SMTPAuthenticationError(535, b"bad credentials")
        FakeSMTP.logins.append(user)

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def mail(env, monkeypatch):
    FakeSMTP.sent, FakeSMTP.logins, FakeSMTP.fail, FakeSMTP.host = [], [], False, None
    monkeypatch.setattr(complaints.email_service.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(complaints.threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    monkeypatch.setattr(complaints, "DAOUsers", lambda: type("U", (), {"get_users": lambda self, uid: {
        "name": "Mai Buyer", "email": "mai@example.com", "phone": "+84901234567"}})())
    for k, v in {"SMTP_PASSWORD": "s3cret-pw", "COMPLAINT_EMAIL_TO": "support@sariko.store", "SMTP_USER": "support@sariko.store",
                 "SMTP_HOST": "smtp.titan.email", "SMTP_PORT": "465", "ADMIN_APP_URL": "https://admin.sariko.store/", "ENV": "dev"}.items():
        monkeypatch.setenv(k, v)
    env.dao.orders["o1"]["id"] = "a805e862-1111-4222-8333-444444444444"
    env.dao.orders["a805e862-1111-4222-8333-444444444444"] = env.dao.orders.pop("o1")
    env.dao.orders["a805e862-1111-4222-8333-444444444444"]["seller_profiles"]["store_name"] = "Rosa Home Kitchen"
    return env


def file(env):
    return env.client.post("/complaints", json={"order_id": "a805e862-1111-4222-8333-444444444444",
                                                "category": "damaged", "description": "Đồ ăn bị đổ, hộp móp"})


def test_email_tc1_sent_to_support(mail):
    res = file(mail)
    assert res.status_code == 200, res.text
    c = res.json()["complaint"]
    assert FakeSMTP.host == ("smtp.titan.email", 465, 30) and FakeSMTP.logins == ["support@sariko.store"]
    (msg,) = FakeSMTP.sent
    assert msg["From"] == "Sariko <support@sariko.store>" and msg["To"] == "support@sariko.store"
    assert msg["Reply-To"] == "mai@example.com"
    assert msg["Subject"] == "[TEST DEV] [Sariko] Khiếu nại mới KN000001 - Hư hỏng / không an toàn"
    body = msg.get_content()
    for line in ("Khiếu nại mới KN000001", "Người gửi: Người mua · Mai Buyer · mai@example.com · +84901234567",
                 "Kênh: Ứng dụng", "Loại: Hư hỏng / không an toàn", "Đơn: #A805E862 · Rosa Home Kitchen",
                 "(giờ Việt Nam)", "Đồ ăn bị đổ, hộp móp", f"Mở trong admin: https://admin.sariko.store/complaints?open={c['id']}",
                 "Ảnh (nếu có): xem trong admin."):
        assert line in body, (line, body)


def test_email_prd_has_no_prefix(mail, monkeypatch):
    monkeypatch.setenv("ENV", "prd")
    file(mail)
    assert FakeSMTP.sent[0]["Subject"].startswith("[Sariko] Khiếu nại mới")


@pytest.mark.parametrize("unset", ["SMTP_PASSWORD", "COMPLAINT_EMAIL_TO"])
def test_email_tc2_not_configured(mail, monkeypatch, unset):
    monkeypatch.delenv(unset)
    res = file(mail)
    assert res.status_code == 200 and FakeSMTP.host is None and FakeSMTP.sent == []   # no SMTP connection at all


def test_email_tc3_smtp_error_keeps_the_complaint(mail, caplog):
    FakeSMTP.fail = True
    res = file(mail)
    assert res.status_code == 200 and res.json()["complaint"]["code"] == "KN000001"
    lines = [r.getMessage() for r in caplog.records if "email not sent" in r.getMessage()]
    assert lines == ["[Complaint] KN000001 email not sent: SMTPAuthenticationError"], lines
    assert "s3cret-pw" not in caplog.text and "Đồ ăn bị đổ" not in caplog.text
