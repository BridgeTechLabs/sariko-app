from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

from clients.supabase import get_supabase_client
from services.order_expiry import run_order_expiry
from services.payment_reconcile import run_payment_reconcile
from services.api_metrics import run_api_metrics
from services.allingo_wallet import run_allingo_wallet

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Supabase client is ready.")
    app.state.supabase = get_supabase_client()
    
    expiry = asyncio.create_task(run_order_expiry())
    reconcile = asyncio.create_task(run_payment_reconcile())
    metrics = asyncio.create_task(run_api_metrics())
    wallet = asyncio.create_task(run_allingo_wallet())

    yield
    expiry.cancel()
    reconcile.cancel()
    metrics.cancel()
    wallet.cancel()
