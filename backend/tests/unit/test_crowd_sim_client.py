"""
Unit tests for Sub-task 2.3a — crowd_sim_client.py

Tests the CrowdSimMCPClient fallback behavior (MCP server unavailable).
All simulated output must carry data_source='SIMULATED' and _fallback=True.

The actual MCPServer in mcp_servers/crowd_sim_mcp/ is tested implicitly —
its crowd_logic.py reuses the same physics model as the backend simulator.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# TestCrowdSimClientFallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrowdSimClientFallback:
    """When MCP server is unreachable, all methods use in-process fallback."""

    @pytest.mark.asyncio
    async def test_simulate_falls_back_when_mcp_unavailable(self):
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()

        client = CrowdSimMCPClient(url="http://localhost:9999/mcp")

        # _call_tool will fail (connection refused → empty dict → fallback)
        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value={}):
            result = await client.simulate_crowd_exit(
                event_id="test-event",
                t_plus_minutes=20,
                attendance=34000,
            )

        assert result["data_source"] == "SIMULATED"
        assert result.get("_fallback") is True

    @pytest.mark.asyncio
    async def test_simulate_fallback_has_total_demand(self):
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()
        client = CrowdSimMCPClient(url="http://localhost:9999/mcp")

        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value={}):
            result = await client.simulate_crowd_exit(
                event_id="test-event",
                t_plus_minutes=20,
                attendance=34000,
            )

        # total_demand must be <= attendance
        assert result["total_demand"] <= 34000
        assert result["total_demand"] >= 0

    @pytest.mark.asyncio
    async def test_simulate_fallback_has_h3_cells(self):
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()
        client = CrowdSimMCPClient(url="http://localhost:9999/mcp")

        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value={}):
            result = await client.simulate_crowd_exit(
                event_id="test-event",
                t_plus_minutes=20,
                attendance=34000,
            )

        # The fallback uses the in-process simulator which generates H3 cells
        assert "h3_cells" in result
        assert len(result["h3_cells"]) > 0

    @pytest.mark.asyncio
    async def test_exit_wave_fallback_returns_wave_series(self):
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()
        client = CrowdSimMCPClient(url="http://localhost:9999/mcp")

        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value={}):
            result = await client.get_exit_wave(event_id="test-event", attendance=34000)

        assert result["data_source"] == "SIMULATED"
        assert result.get("_fallback") is True
        assert "wave" in result
        assert len(result["wave"]) > 0

    @pytest.mark.asyncio
    async def test_h3_cells_fallback_returns_cells(self):
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()
        client = CrowdSimMCPClient(url="http://localhost:9999/mcp")

        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value={}):
            result = await client.get_h3_cells_for_horizon(
                event_id="test-event",
                t_plus_minutes=20,
                attendance=34000,
            )

        assert result["data_source"] == "SIMULATED"
        assert result.get("_fallback") is True
        assert "cells" in result
        assert len(result["cells"]) > 0

    @pytest.mark.asyncio
    async def test_simulate_uses_mcp_result_when_available(self):
        """When _call_tool returns data, use it directly (no fallback)."""
        from app.mcp_servers.crowd_sim_client import CrowdSimMCPClient, reset_client_for_testing
        reset_client_for_testing()
        client = CrowdSimMCPClient(url="http://crowd-sim-mcp:8001/mcp")

        fake_result = {
            "event_id": "test-event",
            "total_demand": 15000,
            "h3_cells": [{"h3_id": "87194ad3fffffff", "demand_persons": 5000}],
            "data_source": "SIMULATED",
            "confidence": 0.82,
        }

        with patch.object(client, "_call_tool", new_callable=AsyncMock, return_value=fake_result):
            result = await client.simulate_crowd_exit(
                event_id="test-event",
                t_plus_minutes=20,
                attendance=34000,
            )

        assert result["total_demand"] == 15000
        assert result.get("_fallback") is None  # not a fallback

    def test_singleton_get_crowd_sim_client(self):
        from app.mcp_servers.crowd_sim_client import get_crowd_sim_client, reset_client_for_testing
        reset_client_for_testing()
        c1 = get_crowd_sim_client()
        c2 = get_crowd_sim_client()
        assert c1 is c2

    def test_reset_creates_new_instance(self):
        from app.mcp_servers.crowd_sim_client import get_crowd_sim_client, reset_client_for_testing
        c1 = get_crowd_sim_client()
        reset_client_for_testing()
        c2 = get_crowd_sim_client()
        assert c1 is not c2
