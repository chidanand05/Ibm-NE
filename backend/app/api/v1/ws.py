"""WebSocket endpoint for real-time agent and approval updates — Sub-task 2.5."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.dependencies import RedisClient
from app.services.ws_manager import get_ws_manager
from app.services.ws_broadcaster import start_redis_subscriber

router = APIRouter()
log = logging.getLogger(__name__)

# Background subscriber task handle (module-level; started once at app startup)
_subscriber_task: asyncio.Task | None = None


async def ensure_redis_subscriber(redis) -> None:
    """
    Start the Redis pub/sub subscriber background task if not already running.
    Called on first WebSocket connection.
    Idempotent — safe to call multiple times.
    """
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        ws_manager = get_ws_manager()
        _subscriber_task = asyncio.create_task(
            start_redis_subscriber(redis, ws_manager),
            name="ws_redis_subscriber",
        )
        log.info("ws.redis_subscriber_started")


@router.websocket("/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: str,
    redis: RedisClient,
) -> None:
    """
    WebSocket endpoint for real-time orchestrator session updates.

    Subscribe to a session to receive:
    - agent_update: per-agent status changes
    - plan_ready: action plan produced and awaiting approval
    - approval_update: officer approved/rejected/sent-back
    - session_complete: all agents finished
    - error: session-level error

    Messages are broadcast via Redis pub/sub → WebSocketManager.
    Human approval is required before any operational action.
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(session_id, websocket)

    # Ensure Redis subscriber is running
    await ensure_redis_subscriber(redis)

    try:
        # Send initial connected message
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": (
                "Connected to Namma Exodus session stream. "
                "All simulation data is SIMULATED. "
                "No operational actions occur without human officer approval."
            ),
        })

        # Keep connection alive; real messages arrive via Redis → ws_manager
        while True:
            try:
                # Wait for client ping or close frame (30-second timeout)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo ping/pong keepalive
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive to detect dead connections
                await websocket.send_json({"type": "keepalive", "session_id": session_id})

    except WebSocketDisconnect:
        log.info("ws.client_disconnected", extra={"session_id": session_id})
    except Exception as exc:
        log.warning("ws.error", extra={"session_id": session_id, "error": str(exc)})
    finally:
        ws_manager.disconnect(session_id, websocket)
