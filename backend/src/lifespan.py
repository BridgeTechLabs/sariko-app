from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

from clients.supabase import get_supabase_client
from services.supabase_realtime import keep_realtime_alive
from services.order_expiry import run_order_expiry

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Supabase client is ready.")
    app.state.supabase = get_supabase_client()
    
    task = asyncio.create_task(keep_realtime_alive())
    expiry = asyncio.create_task(run_order_expiry())

    yield
    task.cancel()
    expiry.cancel()
