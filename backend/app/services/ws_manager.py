"""
WebSocket Manager — Sub-task 2.5.

Manages in-process WebSocket connections per session.
Handles connect/disconnect lifecycle and fan-out to all session subscribers.

Architecture:
    - Each orchestrator session has a session_id.
    - One or more WebSocket clients can subscribe to that session.
    - Messages broadcast to a session_id are delivered to all connected clients.
    - No persistence — connections are in-memory only.
    - Redis pub/sub fan-out is in ws_broadcaster.py.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger(__name__)


class WebSocketManager:
    """
    In-process WebSocket connection registry.

    Thread-safety: operations are called from asyncio tasks running in the
    same event loop (FastAPI's default); the defaultdict is mutated only
    within that loop so no additional locking is required.
    """

    def __init__(self) -> None:
        # session_id → set of connected WebSocket clients
        self._sessions: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection for a session."""
        await websocket.accept()
        self._sessions[session_id].add(websocket)
        log.info("ws.connected", extra={"session_id": session_id, "total": len(self._sessions[session_id])})

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from the session registry."""
        self._sessions[session_id].discard(websocket)
        if not self._sessions[session_id]:
            del self._sessions[session_id]
        log.info("ws.disconnected", extra={"session_id": session_id})

    async def send_to_session(self, session_id: str, message: dict) -> None:
        """Send a JSON message to all WebSocket clients subscribed to a session."""
        connections = list(self._sessions.get(session_id, set()))
        if not connections:
            return

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception as exc:
                log.warning("ws.send_failed", extra={"session_id": session_id, "error": str(exc)})
                dead.append(ws)

        for ws in dead:
            self.disconnect(session_id, ws)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to ALL connected WebSocket clients across all sessions."""
        for session_id in list(self._sessions.keys()):
            await self.send_to_session(session_id, message)

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    @property
    def total_connection_count(self) -> int:
        return sum(len(ws_set) for ws_set in self._sessions.values())


# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: WebSocketManager | None = None


def get_ws_manager() -> WebSocketManager:
    """Return the module-level WebSocketManager singleton."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


def reset_ws_manager_for_testing() -> None:
    """Reset singleton — for use in tests only."""
    global _manager
    _manager = None
