"""
FastAPI application entrypoint.

Wires up:
  - all routers (dashboard, monitoring, retraining, backtest, admin, websocket)
  - startup hooks: initial data backfill, live price streaming task, scheduler
  - CORS for the Next.js frontend
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dashboard, monitoring, retraining, backtest, admin, websocket
from app.services.data_ingestion import backfill_history, stream_live_prices
from app.tasks.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("main")

_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    logger.info("Starting BTC/USDT trading system backend (%s)", settings.ENVIRONMENT)
    try:
        await backfill_history(limit=1000)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Initial backfill failed (will retry on schedule): %s", exc)

    task = asyncio.create_task(stream_live_prices())
    _background_tasks.append(task)

    start_scheduler()

    yield

    # --- shutdown ---
    for t in _background_tasks:
        t.cancel()
    logger.info("Shutting down backend.")


app = FastAPI(
    title="BTC/USDT Probabilistic Trading System API",
    description=(
        "Backend for a probability-based BTC/USDT signal system. "
        "All predictions are probabilistic estimates, never certainties. "
        "See /docs for the full interactive API reference."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(monitoring.router)
app.include_router(retraining.router)
app.include_router(backtest.router)
app.include_router(admin.router)
app.include_router(websocket.router)


@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT, "symbol": settings.SYMBOL}


@app.get("/", tags=["health"])
async def root():
    return {
        "name": "BTC/USDT Probabilistic Trading System",
        "docs": "/docs",
        "disclaimer": "All signals are probability-based estimates, not certainties or financial advice.",
    }
