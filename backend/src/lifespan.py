from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import os

from clients.supabase import get_supabase_client
from services.order_expiry import run_order_expiry
from services.payment_reconcile import run_payment_reconcile
from services.api_metrics import run_api_metrics
from services.allingo_wallet import run_allingo_wallet

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Supabase client is ready.")
    app.state.supabase = get_supabase_client()
    
    # A dev machine (ENV local) shares the DEV database with the DEV server: its jobs would compete (L53). RUN_JOBS=1 runs them.
    run = os.environ.get("ENV", "local") != "local" or os.environ.get("RUN_JOBS") == "1"
    jobs = [asyncio.create_task(job()) for job in (run_order_expiry, run_payment_reconcile, run_api_metrics, run_allingo_wallet)] if run else []

    yield
    for task in jobs:
        task.cancel()
