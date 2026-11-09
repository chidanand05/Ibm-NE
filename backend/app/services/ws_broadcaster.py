"""
WebSocket Broadcaster — Sub-task 2.5.

Redis pub/sub fan-out layer for real-time agent and approval updates.

Architecture:
    - Backend components (agents, orchestrator, approval handler) publish
      messages to Redis channel: ws:{session_id}
    - The WebSocket endpoint subscribes to that channel via Redis pub/sub.
    - Fan-out from Redis → ws_manager.send_to_session is handled by a
      background subscriber task started at app startup.

Channel naming:
    - ws:{session_id}   — messages for a specific orchestrator session
    - ws:broadcast      — messages to all connected clients

Message envelope (all messages must include):
    {
        "type": str,           # agent_update | plan_ready | approval_update | session_complete | error
        "session_id": str,     # which session this belongs to
        "data": dict,          # payload
        "timestamp": str,      # ISO 8601 UTC
    }

All agent-generated content has data_source="SIMULATED" (enforced by agents).
No agent may autonomously issue public instructions (human approval required).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

WS_CHANNEL_PREFIX = "ws:"
WS_BROADCAST_CHANNEL = "ws:broadcast"


# ── Publisher ──────────────────────────────────────────────────────────────────

async def publish_to_session(
    redis,
    session_id: str,
    msg_type: str,
    data: dict[str, Any],
) -> None:
    """
    Publish a message to the session-specific Redis channel.

    Parameters
    ----------
    redis       redis.asyncio.Redis instance
    session_id  Orchestrator session ID
    msg_type    Message type string (e.g. "agent_update", "plan_ready")
    data        Message payload dict
    """
    message = {
        "type": msg_type,
        "session_id": session_id,
        "data": data,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    channel = f"{WS_CHANNEL_PREFIX}{session_id}"
    try:
        await redis.publish(channel, json.dumps(message))
    except Exception as exc:
        log.warning("ws_broadcaster.publish_failed", extra={"channel": channel, "error": str(exc)})


async def publish_broadcast(
    redis,
    msg_type: str,
    data: dict[str, Any],
) -> None:
    """Publish a message to the broadcast channel (all connected clients)."""
    message = {
        "type": msg_type,
        "session_id": None,
        "data": data,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    try:
        await redis.publish(WS_BROADCAST_CHANNEL, json.dumps(message))
    except Exception as exc:
        log.warning("ws_broadcaster.broadcast_failed", extra={"error": str(exc)})


# ── Subscriber task ────────────────────────────────────────────────────────────

async def start_redis_subscriber(redis, ws_manager) -> None:
    """
    Background task: subscribe to Redis and fan-out messages to WebSocket clients.

    Subscribes to the broadcast channel and to per-session channels dynamically
    as sessions are created. Messages are deserialized and forwarded to the
    appropriate WebSocket connections via ws_manager.

    This function runs indefinitely until cancelled (app shutdown).
    """
    pubsub = redis.pubsub()
    await pubsub.psubscribe(f"{WS_CHANNEL_PREFIX}*")  # subscribe to all ws:* channels
    log.info("ws_broadcaster.subscriber_started")

    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] not in ("message", "pmessage"):
                continue
            try:
                payload = json.loads(raw_message["data"])
                session_id = payload.get("session_id")

                if session_id:
                    await ws_manager.send_to_session(session_id, payload)
                else:
                    await ws_manager.broadcast(payload)

            except (json.JSONDecodeError, Exception) as exc:
                log.warning("ws_broadcaster.message_error", extra={"error": str(exc)})

    except asyncio.CancelledError:
        log.info("ws_broadcaster.subscriber_stopped")
    finally:
        await pubsub.punsubscribe(f"{WS_CHANNEL_PREFIX}*")
        await pubsub.close()
