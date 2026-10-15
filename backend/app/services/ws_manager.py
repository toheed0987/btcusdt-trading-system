"""
WebSocket connection manager: tracks connected dashboard clients and
broadcasts price/signal updates received from the Redis pub/sub channels.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

from app.services import redis_cache

logger = logging.getLogger("ws_manager")


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._pubsub_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def start_redis_listener(self):
        """Subscribes to Redis pub/sub and forwards messages to all connected clients."""
        if self._pubsub_task is not None:
            return
        self._pubsub_task = asyncio.create_task(self._listen())

    async def _listen(self):
        r = redis_cache.get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(redis_cache.PRICE_CHANNEL, redis_cache.SIGNAL_CHANNEL)
        logger.info("Subscribed to Redis channels for WebSocket fan-out")
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                payload = json.loads(message["data"])
                await self.broadcast(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to forward pubsub message: %s", exc)


manager = ConnectionManager()
