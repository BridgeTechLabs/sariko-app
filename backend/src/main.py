import os
import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(dotenv_path=f"envs/.env.{os.environ.get('ENV', 'local')}")
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


from apis import (
    users, sellers, cart, orders, payments, deliveries,
    address, admin_refunds, moit, search, chat, reviews
)

log_level = logging.WARNING
formatter = logging.Formatter(
    fmt="%(asctime)s - %(module)s - %(levelname)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S', 
)

if not os.path.exists('logs'):
    os.makedirs('logs')
time_rotate_file_handler = TimedRotatingFileHandler(filename="logs/app.log", when="midnight")
time_rotate_file_handler.setLevel(log_level)
time_rotate_file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(log_level)
stream_handler.setFormatter(formatter)

logging.basicConfig(
    datefmt="%Y-%m-%d %H:%M:%S%z" ,
    level=log_level,
    handlers=[stream_handler, time_rotate_file_handler]
)

logger = logging.getLogger(__name__)

from lifespan import lifespan
app = FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request data", "errors": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {repr(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

app.include_router(users.router, prefix="/rest/v1", tags=["v1"])
app.include_router(sellers.router, prefix="/rest/v1", tags=["v1"])
app.include_router(cart.router, prefix="/rest/v1", tags=["v1"])
app.include_router(orders.router, prefix="/rest/v1", tags=["v1"])
app.include_router(payments.router, prefix="/rest/v1", tags=["v1"])
app.include_router(deliveries.router, prefix="/rest/v1", tags=["v1"])
app.include_router(address.router, prefix="/rest/v1", tags=["v1"])
app.include_router(search.router, prefix="/rest/v1", tags=["v1"])
app.include_router(chat.router, prefix="/rest/v1", tags=["v1"])
app.include_router(reviews.router, prefix="/rest/v1", tags=["v1"])
if os.environ.get("ENV", "local") in ("local", "dev"):
    from apis import dev
    app.include_router(dev.router, prefix="/rest/v1", tags=["dev"])
app.include_router(admin_refunds.router, prefix="/rest/v1", tags=["admin"])
app.include_router(moit.router, prefix="/rest/v1", tags=["moit"])

# Registered BEFORE CORSMiddleware so CORS stays the outermost middleware.
# FastAPI's @app.exception_handler(Exception) runs in ServerErrorMiddleware, which
# sits outside CORS — its 500 response carries no Access-Control-Allow-Origin, so
# the browser blocks it and the frontend sees a misleading "Network Error".
@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception(f"Unhandled error: {repr(exc)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "https://sariko.pages.dev",
        "https://app.sariko.store",
        os.getenv("CORS_EXTRA_ORIGIN", ""),  # set to ngrok URL if needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def get_health():
    return {
        "success": True, 
        "status": "ok", 
        "version": os.environ.get("IMAGE_TAG", "0000"), 
        "service": "sariko-api"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)