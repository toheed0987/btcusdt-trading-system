"""
WebSocket endpoint for live dashboard updates (price ticks + fresh signals).
Frontend connects to ws://<host>/ws/live and receives JSON messages of the
shape {"type": "price", ...} or {"type": "signal", ...}.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await manager.connect(ws)
    await manager.start_redis_listener()
    try:
        while True:
            # We don't require client -> server messages, but keep the
            # receive loop alive so disconnects are detected promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
