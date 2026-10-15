"""
Thin async Redis wrapper used for:
  - caching the latest signal / price (fast dashboard reads)
  - pub/sub fan-out to WebSocket clients across workers
"""
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.config import settings

_pool: Optional[redis.Redis] = None

LATEST_PRICE_KEY = "btc:latest_price"
LATEST_SIGNAL_KEY = "btc:latest_signal"
PRICE_CHANNEL = "btc:price_channel"
SIGNAL_CHANNEL = "btc:signal_channel"


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


async def set_json(key: str, value: Any, ex_seconds: int = 3600):
    r = get_redis()
    await r.set(key, json.dumps(value, default=str), ex=ex_seconds)


async def get_json(key: str) -> Optional[Any]:
    r = get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def publish(channel: str, message: dict):
    r = get_redis()
    await r.publish(channel, json.dumps(message, default=str))
