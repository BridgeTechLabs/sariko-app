"""dev-guards (docs/dev/20261110-dev-guards): a dev machine (ENV local) runs no background jobs unless RUN_JOBS=1, its
jobs would compete with the DEV server on the same database (L53); migration files are <14 digits>_<name>.sql, no number
used twice. No DB, no network."""
import asyncio
import re
from collections import Counter
from pathlib import Path

import pytest

import lifespan

# CI mounts backend/supabase/migrations at /backend/supabase/migrations, the same place relative to /tests as in the repo
MIGRATIONS = Path(__file__).resolve().parents[3] / "backend" / "supabase" / "migrations"
JOBS = ("run_order_expiry", "run_payment_reconcile", "run_api_metrics", "run_allingo_wallet")


def started_jobs(monkeypatch, env, run_jobs=None):
    started = []
    for name in JOBS:
        async def job(name=name):
            started.append(name)
        monkeypatch.setattr(lifespan, name, job)
    monkeypatch.setattr(lifespan, "get_supabase_client", lambda: None)
    monkeypatch.setenv("ENV", env)
    if run_jobs:
        monkeypatch.setenv("RUN_JOBS", run_jobs)
    else:
        monkeypatch.delenv("RUN_JOBS", raising=False)

    async def serve():
        app = type("App", (), {"state": type("State", (), {})()})()
        async with lifespan.lifespan(app):
            await asyncio.sleep(0)   # let started tasks run once

    asyncio.run(serve())
    return sorted(started)


def test_tc1_dev_machine_runs_no_jobs(monkeypatch):
    assert started_jobs(monkeypatch, "local") == []
    assert started_jobs(monkeypatch, "local", run_jobs="0") == []


@pytest.mark.parametrize("env, run_jobs", [("local", "1"), ("dev", None), ("prod", None)])
def test_tc2_servers_and_run_jobs_run_every_job(monkeypatch, env, run_jobs):
    assert started_jobs(monkeypatch, env, run_jobs) == sorted(JOBS)


def test_tc3_migration_numbers_are_unique():
    names = [p.name for p in MIGRATIONS.glob("*.sql")]
    assert names, f"no migrations at {MIGRATIONS} (CI must mount backend/supabase/migrations)"
    assert [n for n in names if not re.fullmatch(r"\d{14}_\w+\.sql", n)] == []
    assert [num for num, n in Counter(n[:14] for n in names).items() if n > 1] == [], "migration number used twice"
