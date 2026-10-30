"""
API snapshot (regression-baseline R2)
=====================================
Manual script, not run by pytest. Records what every GET of an API answers (status + JSON key shape, NEVER values:
personal data) so the same run before and after a refactor, or on DEV and PROD, can be compared.

Run from project root:
    python3 -I tests/manual/api_snapshot.py take <api base URL> <buyer|seller|admin> <out.json>
    python3 -I tests/manual/api_snapshot.py diff <before.json> <after.json>
e.g. take https://api-dev.sariko.store buyer before.json / take https://api-admin-dev.sariko.store admin before.json

take: reads <base>/openapi.json, logs in as the DEV_<ROLE>_* test account (.config/sariko/dummy_creds; Supabase URL and
anon key from frontend/.env.development; nothing printed), then calls every GET with no required query parameter. A path parameter
is filled with the first id / slug found in an earlier answer (see fill); none found -> recorded as skipped. Only GET goes to the API (the login is a POST
to Supabase Auth). Routes are recorded by their template (/orders/{order_id}), so two runs line up.
diff: prints the routes whose status changed, that appear in only one file, or whose keys were added / removed.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# GETs left out on purpose, with why.
SKIP = {
    "/rest/v1/payments/vnpay/ipn": "VNPay server callback",
    "/rest/v1/payments/vnpay/return": "VNPay browser redirect",
    "/rest/v1/admin/menu/inspect": "a GET that deletes the menu-import folder on the server",
}


def env_file(path):
    out = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def req(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            status, txt = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, txt = e.code, e.read()
    try:
        return status, json.loads(txt) if txt else None
    except ValueError:
        return status, "<not json>"


def login(role):
    creds = env_file(ROOT / ".config/sariko/dummy_creds")
    front = env_file(ROOT / "frontend/.env.development")
    s, d = req("POST", f"{front['VITE_SUPABASE_URL'].rstrip('/')}/auth/v1/token?grant_type=password",
               {"email": creds[f"DEV_{role.upper()}_EMAIL"], "password": creds[f"DEV_{role.upper()}_PASSWORD"]},
               {"apikey": front["VITE_SUPABASE_ANON_KEY"]})
    if s != 200:
        sys.exit(f"login as {role} failed: HTTP {s}")
    return {"Authorization": f"Bearer {d['access_token']}"}


def shape(v):
    """Keys only: a dict -> {key: shape}, a list -> [merged shape of its items], anything else -> None."""
    if isinstance(v, dict):
        return {k: shape(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        merged = None
        for item in v:
            merged = merge(merged, shape(item))
        return [merged] if v else []
    return None


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: merge(a.get(k), b.get(k)) for k in sorted(set(a) | set(b))}
    return a if a is not None else b


def rows(answer):
    """The list of dicts in an answer: the answer itself, or the first such list among its values."""
    for v in [answer] + (list(answer.values()) if isinstance(answer, dict) else []):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def fill(template, param, answers):
    """A value for {param}: the list one level up, else a list whose path names the same thing (order_id <- .../orders),
    else for a slug any answer. A value can sit one level down (featured dishes -> seller_profiles.slug)."""
    key = "id" if param.endswith("_id") else ("slug" if "slug" in param else param)
    noun = re.sub(r"_(id|name)$", "", param)
    parent = template.split("{")[0].rstrip("/")
    sources = [a for p, a in answers.items() if p.rstrip("/") == parent]
    sources += [a for p, a in answers.items() if noun in p]
    if key != "id":   # an id from an unrelated list would point at the wrong thing
        sources += list(answers.values())
    for answer in sources:
        for row in rows(answer):
            for item in [row] + [v for v in row.values() if isinstance(v, dict)]:
                value = item.get(param) or item.get(key)
                if value:
                    return str(value)
    return None


def take(base, role, out):
    base = base.rstrip("/")
    s, spec = req("GET", f"{base}/openapi.json")
    if s != 200:
        sys.exit(f"{base}/openapi.json: HTTP {s}")
    auth = login(role)
    gets = sorted((p, op) for p, item in spec["paths"].items() for m, op in item.items() if m == "get")
    routes, answers = {}, {}
    # no path parameter first: their answers give the ids for the others
    for path, op in sorted(gets, key=lambda g: "{" in g[0]):
        name = f"GET {path}"
        params = op.get("parameters", [])
        if path in SKIP:
            routes[name] = {"skipped": SKIP[path]}
            continue
        if any(p.get("required") and p["in"] == "query" for p in params):
            routes[name] = {"skipped": "needs a query parameter"}
            continue
        url = path
        for p in [p for p in params if p["in"] == "path"]:
            value = fill(path, p["name"], answers)
            if value is None:
                url = None
                break
            url = url.replace("{" + p["name"] + "}", urllib.request.quote(value, safe=""))
        if url is None:
            routes[name] = {"skipped": "no id found in earlier answers"}
            continue
        status, answer = req("GET", base + url, headers=auth)
        answers[path] = answer
        routes[name] = {"status": status, "shape": shape(answer)}
        print(f"{status} {path}")
    Path(out).write_text(json.dumps({"base": base, "role": role, "taken_at": datetime.now(timezone.utc).isoformat(),
                                     "routes": routes}, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(routes)} routes -> {out}")


def keys(v, prefix=""):
    """Every key path of a shape: orders[].id, success, ..."""
    if isinstance(v, dict):
        return {k for key, sub in v.items() for k in {prefix + key} | keys(sub, prefix + key + ".")}
    if isinstance(v, list) and v:
        return keys(v[0], prefix.rstrip(".") + "[].")
    return set()


def diff(before, after):
    a, b = (json.loads(Path(f).read_text())["routes"] for f in (before, after))
    changed = 0
    for route in sorted(set(a) | set(b)):
        x, y = a.get(route), b.get(route)
        lines = []
        if x is None or y is None:
            lines.append("only in " + (after if x is None else before))
        elif x.get("status") != y.get("status") or x.get("skipped") != y.get("skipped"):
            lines.append(f"status {x.get('status', x.get('skipped'))} -> {y.get('status', y.get('skipped'))}")
        if x and y and "shape" in x and "shape" in y:
            kx, ky = keys(x["shape"]), keys(y["shape"])
            lines += [f"+ {k}" for k in sorted(ky - kx)] + [f"- {k}" for k in sorted(kx - ky)]
        if lines:
            changed += 1
            print(route)
            for line in lines:
                print("   ", line)
    print(f"{changed} of {len(set(a) | set(b))} routes differ")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "take" and sys.argv[3] in ("buyer", "seller", "admin"):
        take(*sys.argv[2:])
    elif len(sys.argv) == 4 and sys.argv[1] == "diff":
        diff(*sys.argv[2:])
    else:
        sys.exit(__doc__)
