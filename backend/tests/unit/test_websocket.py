"""
Unit tests for Sub-task 2.5 — WebSocket infrastructure.

Covers:
- ws_manager.py   — connection registry, send, broadcast, disconnect
- ws_broadcaster.py — publish functions, message structure
- ws.py           — ensure_redis_subscriber idempotency

No Docker, no Redis, no live WebSockets required.
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebSocketManager
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebSocketManager:

    def _make_mock_ws(self):
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        await mgr.connect("session-1", ws)
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        await mgr.connect("session-1", ws)
        assert mgr.total_connection_count == 1
        assert mgr.active_session_count == 1

    @pytest.mark.asyncio
    async def test_multiple_connections_same_session(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws1 = self._make_mock_ws()
        ws2 = self._make_mock_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-1", ws2)
        assert mgr.total_connection_count == 2
        assert mgr.active_session_count == 1  # still one session

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        await mgr.connect("session-1", ws)
        mgr.disconnect("session-1", ws)
        assert mgr.total_connection_count == 0
        assert mgr.active_session_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_session_is_noop(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        # Disconnecting from a session we never connected to must not raise
        mgr.disconnect("nonexistent", ws)
        assert mgr.total_connection_count == 0

    @pytest.mark.asyncio
    async def test_send_to_session_delivers_message(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        await mgr.connect("session-1", ws)
        msg = {"type": "agent_update", "agent_id": "supply", "data_source": "SIMULATED"}
        await mgr.send_to_session("session-1", msg)
        ws.send_json.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_send_to_session_multiple_clients(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws1 = self._make_mock_ws()
        ws2 = self._make_mock_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-1", ws2)
        msg = {"type": "plan_ready"}
        await mgr.send_to_session("session-1", msg)
        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_send_to_empty_session_is_noop(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        # Should not raise
        await mgr.send_to_session("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_send_to_session_removes_dead_connections(self):
        """Failed send_json should remove the dead WebSocket."""
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws = self._make_mock_ws()
        ws.send_json.side_effect = RuntimeError("connection closed")
        await mgr.connect("session-1", ws)
        await mgr.send_to_session("session-1", {"type": "test"})
        # Dead connection should be removed
        assert mgr.total_connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_all_sessions(self):
        from app.services.ws_manager import WebSocketManager
        mgr = WebSocketManager()
        ws1 = self._make_mock_ws()
        ws2 = self._make_mock_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-2", ws2)
        msg = {"type": "system_alert"}
        await mgr.broadcast(msg)
        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    def test_singleton_returns_same_instance(self):
        from app.services.ws_manager import get_ws_manager, reset_ws_manager_for_testing
        reset_ws_manager_for_testing()
        m1 = get_ws_manager()
        m2 = get_ws_manager()
        assert m1 is m2

    def test_reset_creates_fresh_manager(self):
        from app.services.ws_manager import get_ws_manager, reset_ws_manager_for_testing
        m1 = get_ws_manager()
        reset_ws_manager_for_testing()
        m2 = get_ws_manager()
        assert m1 is not m2


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebSocketBroadcaster
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebSocketBroadcaster:

    @pytest.mark.asyncio
    async def test_publish_to_session_sends_to_redis(self):
        from app.services.ws_broadcaster import publish_to_session
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        await publish_to_session(
            redis=mock_redis,
            session_id="sess-1",
            msg_type="agent_update",
            data={"agent_id": "supply", "data_source": "SIMULATED"},
        )
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_to_session_channel_format(self):
        from app.services.ws_broadcaster import publish_to_session
        mock_redis = AsyncMock()
        channel_used = []
        message_sent = []

        async def capture_publish(channel, message):
            channel_used.append(channel)
            message_sent.append(message)

        mock_redis.publish = capture_publish

        await publish_to_session(
            redis=mock_redis,
            session_id="sess-abc",
            msg_type="plan_ready",
            data={"plan_id": "plan-1"},
        )

        assert channel_used[0] == "ws:sess-abc"
        payload = json.loads(message_sent[0])
        assert payload["type"] == "plan_ready"
        assert payload["session_id"] == "sess-abc"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_publish_to_session_redis_error_is_suppressed(self):
        """A Redis publish failure must not crash the caller."""
        from app.services.ws_broadcaster import publish_to_session
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(side_effect=Exception("redis down"))

        # Should not raise
        await publish_to_session(
            redis=mock_redis,
            session_id="sess-1",
            msg_type="agent_update",
            data={},
        )

    @pytest.mark.asyncio
    async def test_publish_broadcast_sends_to_broadcast_channel(self):
        from app.services.ws_broadcaster import publish_broadcast, WS_BROADCAST_CHANNEL
        mock_redis = AsyncMock()
        channels = []

        async def capture_publish(channel, message):
            channels.append(channel)

        mock_redis.publish = capture_publish

        await publish_broadcast(redis=mock_redis, msg_type="system_alert", data={})
        assert channels[0] == WS_BROADCAST_CHANNEL

    @pytest.mark.asyncio
    async def test_publish_broadcast_none_session_id(self):
        from app.services.ws_broadcaster import publish_broadcast
        mock_redis = AsyncMock()
        messages_sent = []

        async def capture_publish(channel, message):
            messages_sent.append(json.loads(message))

        mock_redis.publish = capture_publish

        await publish_broadcast(redis=mock_redis, msg_type="heartbeat", data={"status": "ok"})
        assert messages_sent[0]["session_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebSocketEndpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebSocketEndpoint:

    @pytest.mark.asyncio
    async def test_ensure_redis_subscriber_creates_task(self):
        from app.api.v1 import ws as ws_module
        # Reset state
        ws_module._subscriber_task = None

        mock_redis = AsyncMock()
        mock_ws_manager = MagicMock()

        async def fake_subscriber(redis, ws_manager):
            await asyncio.sleep(0)

        with patch("app.api.v1.ws.start_redis_subscriber", fake_subscriber):
            with patch("app.api.v1.ws.get_ws_manager", return_value=mock_ws_manager):
                await ws_module.ensure_redis_subscriber(mock_redis)

        assert ws_module._subscriber_task is not None

        # Cleanup
        if ws_module._subscriber_task and not ws_module._subscriber_task.done():
            ws_module._subscriber_task.cancel()
            try:
                await ws_module._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
        ws_module._subscriber_task = None

    @pytest.mark.asyncio
    async def test_ensure_redis_subscriber_idempotent(self):
        """Calling ensure_redis_subscriber twice must not create two tasks."""
        from app.api.v1 import ws as ws_module
        ws_module._subscriber_task = None

        mock_redis = AsyncMock()
        call_count = [0]

        async def fake_subscriber(redis, ws_manager):
            call_count[0] += 1
            await asyncio.sleep(100)  # long-running

        with patch("app.api.v1.ws.start_redis_subscriber", fake_subscriber):
            with patch("app.api.v1.ws.get_ws_manager", return_value=MagicMock()):
                await ws_module.ensure_redis_subscriber(mock_redis)
                first_task = ws_module._subscriber_task
                await ws_module.ensure_redis_subscriber(mock_redis)
                second_task = ws_module._subscriber_task

        # Should be the same task
        assert first_task is second_task

        # Cleanup
        if ws_module._subscriber_task and not ws_module._subscriber_task.done():
            ws_module._subscriber_task.cancel()
            try:
                await ws_module._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
        ws_module._subscriber_task = None
