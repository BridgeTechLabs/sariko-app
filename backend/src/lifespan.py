from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

from clients.supabase import get_supabase_client
from services.supabase_realtime import keep_realtime_alive
from services.order_expiry import run_order_expiry
from services.payment_reconcile import run_payment_reconcile

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Supabase client is ready.")
    app.state.supabase = get_supabase_client()
    
    task = asyncio.create_task(keep_realtime_alive())
    expiry = asyncio.create_task(run_order_expiry())
    reconcile = asyncio.create_task(run_payment_reconcile())

    yield
    task.cancel()
    expiry.cancel()
    reconcile.cancel()
