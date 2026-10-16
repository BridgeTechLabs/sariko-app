"""
DEV history tables check
========================
Manual script — hits the DEV API and DEV Supabase with the DEV_* test accounts. Not run by pytest.

Run from project root:
    python3 -I tests/manual/check_dev_history.py

Reads (all gitignored, nothing printed): .config/sariko/dummy_creds (DEV_BUYER_*, DEV_SELLER_*),
backend/src/envs/.env.dev (service key, read-only DB checks), frontend/.env.development (anon key),
~/.supabase/access-token (Management API, auth config).

Flow:
  1. Auth config      — password_min_length on DEV (expect 8, T48)
  2. history_menu     — seller changes a dish price +1000 then back → 2 rows with the old prices (T31)
  3. Order flow       — buyer orders the first same-day dish (fee from the 409 quote, R1) → force-pay →
                        seller confirms → ready (books a Lalamove sandbox trip)
                        → history_order_status: pending, confirmed, ready; history_delivery: ASSIGNING_DRIVER (T84)
  4. Cleanup          — cancels the Lalamove trip and force-cancels the order
                        → history_order_status: + cancelled; history_delivery: + CANCELLED
Leaves behind: one cancelled test order (note "TEST history tables"), the buyer's DEV cart emptied.
Sandbox never assigns a driver, so driver fields stay empty here.
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF = "saphxhqpjrhdsqbtnwqe"
SB = f"https://{REF}.supabase.co"
API = "https://api-dev.sariko.store/rest/v1"


def env_file(path):
    out = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


creds = env_file(ROOT / ".config/sariko/dummy_creds")
ANON = env_file(ROOT / "frontend/.env.development")["VITE_SUPABASE_ANON_KEY"]
SERVICE = env_file(ROOT / "backend/src/envs/.env.dev")["SUPABASE_API_KEY"]


def req(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            txt = resp.read().decode()
            return resp.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt


def login(prefix):
    s, d = req("POST", f"{SB}/auth/v1/token?grant_type=password",
               {"email": creds[f"{prefix}_EMAIL"], "password": creds[f"{prefix}_PASSWORD"]}, {"apikey": ANON})
    assert s == 200, (prefix, s, d)
    return {"Authorization": f"Bearer {d['access_token']}"}


def db(path):
    s, d = req("GET", f"{SB}/rest/v1/{path}", headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"})
    assert s == 200, (path, s, d)
    return d


def check_auth_config():
    token = Path("~/.supabase/access-token").expanduser().read_text().strip()
    s, d = req("GET", f"https://api.supabase.com/v1/projects/{REF}/config/auth",
               headers={"Authorization": f"Bearer {token}"})
    n = d.get("password_min_length") if isinstance(d, dict) else d
    print(f"1. password_min_length = {n}", "OK" if n == 8 else "← expected 8 (Supabase DEV → Auth → Email)")


def check_history_menu(seller):
    s, d = req("GET", f"{API}/sellers/me/menu", headers=seller)
    item = next(i for c in d["menu"] for i in (c.get("food_items") or []))
    count = lambda: len(db(f"history_menu?row_id=eq.{item['id']}&select=id"))
    before, price = count(), float(item["price"])
    for p in (price + 1000, price):
        s, r = req("PATCH", f"{API}/sellers/me/menu/items/{item['id']}", {"price": p}, seller)
        assert s == 200, (s, r)
    added = count() - before
    print(f"2. history_menu: {item['name']!r} {price:.0f} → +1000 → back: {added} new rows", "OK" if added == 2 else "← expected 2")


def check_order_flow(buyer, seller):
    s, d = req("GET", f"{API}/sellers/me/menu", headers=seller)
    item = next(i for c in d["menu"] for i in (c.get("food_items") or [])
                if i.get("is_available") and not i.get("preorder_day") and not i.get("food_item_variants"))
    seller_id = db(f"food_items?id=eq.{item['id']}&select=seller_id")[0]["seller_id"]
    s, r = req("GET", f"{API}/users/me/address", headers=buyer)
    addr = r["address"]

    req("DELETE", f"{API}/cart/clear", headers=buyer)
    s, r = req("POST", f"{API}/cart/add", {"seller_id": seller_id, "food_item_id": item["id"], "quantity": 1}, buyer)
    assert s == 200, ("cart add", s, r)
    body = {"delivery_method": "delivery", "delivery_address": addr["address"], "delivery_lat": addr["lat"],
            "delivery_lon": addr["lon"], "delivery_fee": 0, "note": "TEST history tables - ignore"}
    s, r = req("POST", f"{API}/orders", body, buyer)
    assert s == 409, ("expected the fee check to refuse fee 0", s, r)
    body["delivery_fee"] = r["detail"]["delivery_fee"]
    s, r = req("POST", f"{API}/orders", body, buyer)
    assert s == 200, ("create order", s, r)
    oid = (r.get("order") or r)["id"]
    print(f"3. order {oid} ({item['name']}, fee {body['delivery_fee']})")

    for step, (method, path, payload, who) in {
        "force-pay": ("PATCH", f"/dev/orders/{oid}/force-pay", {}, buyer),
        "confirmed": ("PATCH", f"/sellers/me/orders/{oid}/status", {"status": "confirmed"}, seller),
        "ready": ("PATCH", f"/sellers/me/orders/{oid}/status", {"status": "ready"}, seller),
    }.items():
        s, r = req(method, f"{API}{path}", payload, who)
        assert s == 200, (step, s, r)
        time.sleep(2)
    report(oid, ["pending", "confirmed", "ready"], ["ASSIGNING_DRIVER"])
    return oid


def cleanup(oid, buyer):
    s, r = req("DELETE", f"{API}/deliveries/{oid}/cancel", headers=buyer)
    print(f"4. cancel Lalamove trip: {s}")
    s, r = req("PATCH", f"{API}/dev/orders/{oid}/force-status", {"status": "cancelled"}, buyer)
    assert s == 200, ("force cancel", s, r)
    report(oid, ["pending", "confirmed", "ready", "cancelled"], ["ASSIGNING_DRIVER", "CANCELLED"])


def report(oid, want_status, want_delivery):
    got_status = [r["status"] for r in db(f"history_order_status?order_id=eq.{oid}&select=status&order=id")]
    got_delivery = [r["status"] for r in db(f"history_delivery?order_id=eq.{oid}&select=status&order=id")]
    print(f"   history_order_status {got_status}", "OK" if got_status == want_status else f"← expected {want_status}")
    print(f"   history_delivery     {got_delivery}", "OK" if got_delivery[:len(want_delivery)] == want_delivery else f"← expected {want_delivery}")


if __name__ == "__main__":
    check_auth_config()
    buyer, seller = login("DEV_BUYER"), login("DEV_SELLER")
    check_history_menu(seller)
    order_id = check_order_flow(buyer, seller)
    cleanup(order_id, buyer)
