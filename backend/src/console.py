"""
Interactive console (like `rails console`).

Run from backend/src:
    python -i console.py                 # envs/.env.local
    ENV=dev python -i console.py         # envs/.env.dev

Every class and function defined in the packages below is loaded by its own name
(DAOOrders, get_token_manager, to_e164_vn, ...) — new files are picked up without
editing this one. On a name clash the first module (alphabetical) wins; the rest
are listed at startup, import those by hand.

Every call is REAL: DAOs hit the Supabase project of the loaded env,
services hit Lalamove / VNPAY with the loaded credentials.
"""
import importlib
import inspect
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ENV = os.environ.get("ENV", "local")
load_dotenv(dotenv_path=f"envs/.env.{ENV}")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

PACKAGES = ["apis", "clients", "core", "dao", "schemas", "services", "utils"]
# Scripts that do their work at import time — importing them here would run them.
SKIP = {"utils.image_compressor"}

from core.sariko_cache import cache

_loaded, _skipped, _clashes = [], [], []
for _path in sorted(p for pkg in PACKAGES for p in Path(pkg).rglob("*.py") if "__pycache__" not in p.parts):
    _parts = _path.with_suffix("").parts
    _name = ".".join(_parts[:-1] if _parts[-1] == "__init__" else _parts)
    if _name in SKIP:
        continue
    try:
        _m = importlib.import_module(_name)
    except Exception as e:
        _skipped.append(f"{_name} ({e})")
        continue
    _loaded.append(_name)
    for _k, _v in vars(_m).items():
        if _k.startswith("_") or not (inspect.isclass(_v) or inspect.isfunction(_v)) or _v.__module__ != _m.__name__:
            continue
        if _k in globals() and globals()[_k] is not _v:
            _clashes.append(f"{_k} ({_name})")
            continue
        globals()[_k] = _v

print(f"Sariko console — ENV={ENV}, {len(_loaded)} modules loaded from {', '.join(PACKAGES)} (+ cache)")
if _skipped:
    print("Skipped:", "; ".join(_skipped))
if _clashes:
    print("Name clashes, not loaded:", ", ".join(_clashes))
