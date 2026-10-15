"""
Data ingestion service:
  - `backfill_history()` pulls historical 1m klines via Binance's public REST
    endpoint (no API key required for market data) to seed the database.
  - `stream_live_prices()` connects to Binance's public kline WebSocket for
    live 1-minute candle updates, persists closed candles, and republishes
    ticks to Redis so the WebSocket router can fan them out to browser clients.

Design note: this module only reads public market data. It never places
orders — order/paper-trading execution is handled separately and gated by
the Admin Panel's `trading_enabled` flag and risk settings.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
import pandas as pd
import websockets
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import OHLCV
from app.services import redis_cache

logger = logging.getLogger("data_ingestion")


async def backfill_history(symbol: str = None, interval: str = "1m", limit: int = 1000) -> int:
    """Fetch recent historical candles from Binance REST and upsert into ohlcv."""
    symbol = symbol or settings.SYMBOL
    url = f"{settings.BINANCE_REST_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        raw = resp.json()

    rows = []
    for k in raw:
        rows.append({
            "symbol": symbol,
            "open_time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
            "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
            "close": float(k[4]), "volume": float(k[5]),
            "interval": interval,
        })

    async with AsyncSessionLocal() as session:
        for row in rows:
            stmt = pg_insert(OHLCV).values(**row).on_conflict_do_update(
                index_elements=["symbol", "interval", "open_time"],
                set_={"close": row["close"], "high": row["high"], "low": row["low"],
                      "volume": row["volume"]},
            )
            await session.execute(stmt)
        await session.commit()

    logger.info("Backfilled %d candles for %s", len(rows), symbol)
    return len(rows)


async def get_recent_ohlcv_df(symbol: str = None, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
    symbol = symbol or settings.SYMBOL
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OHLCV)
            .where(OHLCV.symbol == symbol, OHLCV.interval == interval)
            .order_by(OHLCV.open_time.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    rows = list(reversed(rows))
    df = pd.DataFrame([{
        "open_time": r.open_time, "open": float(r.open), "high": float(r.high),
        "low": float(r.low), "close": float(r.close), "volume": float(r.volume),
    } for r in rows])
    return df


async def stream_live_prices(symbol: str = None):
    """
    Long-running task: connects to Binance's public kline websocket stream,
    persists each closed 1m candle, and publishes every tick (open or closed)
    to Redis for real-time dashboard updates.
    """
    symbol = (symbol or settings.SYMBOL).lower()
    url = settings.BINANCE_WS_URL

    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                logger.info("Connected to live price stream: %s", url)
                async for message in ws:
                    data = json.loads(message)
                    k = data.get("k", {})
                    if not k:
                        continue

                    price = float(k["c"])
                    await redis_cache.set_json(redis_cache.LATEST_PRICE_KEY, {
                        "symbol": symbol.upper(), "price": price,
                        "time": datetime.now(timezone.utc).isoformat(),
                    }, ex_seconds=120)
                    await redis_cache.publish(redis_cache.PRICE_CHANNEL, {
                        "type": "price", "symbol": symbol.upper(), "price": price,
                        "open_time": k["t"], "is_closed": k["x"],
                    })

                    if k["x"]:  # candle closed -> persist
                        row = {
                            "symbol": symbol.upper(),
                            "open_time": datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
                            "open": float(k["o"]), "high": float(k["h"]),
                            "low": float(k["l"]), "close": float(k["c"]),
                            "volume": float(k["v"]), "interval": "1m",
                        }
                        async with AsyncSessionLocal() as session:
                            stmt = pg_insert(OHLCV).values(**row).on_conflict_do_nothing(
                                index_elements=["symbol", "interval", "open_time"]
                            )
                            await session.execute(stmt)
                            await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Live price stream error, reconnecting in 5s: %s", exc)
            await asyncio.sleep(5)
