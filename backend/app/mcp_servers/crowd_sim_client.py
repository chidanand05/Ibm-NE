"""
Crowd Simulation MCP Client — Sub-task 2.3a.

HTTP client for the standalone crowd-sim-mcp Streamable HTTP MCP server.

This module is used by the backend agents to call crowd simulation tools
via the MCP protocol. It wraps the three registered tools:
  - simulate_crowd_exit
  - get_exit_wave
  - get_h3_cells_for_horizon

Architecture note:
  The crowd-sim-mcp server runs as a separate Docker service at
  http://crowd-sim-mcp:8001/mcp. This client calls it using the MCP
  streamable HTTP transport.

  In tests (no Docker), the CROWD_SIM_MCP_URL can be overridden via
  environment variable, and a fallback in-process simulation is used
  when the MCP server is unavailable (clearly labeled SIMULATED).

Fallback behavior:
  If the MCP server is unreachable, all methods fall back to the local
  in-process simulator (backend/app/simulator/crowd.py). Fallback is
  logged with level WARNING and data_source always remains "SIMULATED".
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)

# ── Fallback: in-process simulator ───────────────────────────────────────────
# Used when crowd-sim-mcp Docker service is not reachable.

def _fallback_simulate(
    event_id: str,
    t_plus_minutes: int,
    attendance: int,
    venue_lat: float = 12.9789,
    venue_lon: float = 77.5996,
    random_seed: int = 42,
) -> dict:
    """Fallback to in-process simulator when MCP server is unavailable."""
    from app.simulator.crowd import simulate_crowd_exit  # noqa: PLC0415
    from app.seed.constants import CHINNASWAMY_GATES  # noqa: PLC0415
    result = simulate_crowd_exit(
        event_id=event_id,
        t_plus_minutes=t_plus_minutes,
        attendance=attendance,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        gates=CHINNASWAMY_GATES,
        random_seed=random_seed,
    )
    # Convert Pydantic model to dict for uniform interface
    d = result.model_dump()
    d["_fallback"] = True
    d["_fallback_reason"] = "crowd-sim-mcp unavailable; using in-process simulator"
    return d


def _fallback_exit_wave(event_id: str, attendance: int, random_seed: int = 42) -> dict:
    from app.simulator.crowd import build_exit_wave  # noqa: PLC0415
    wave = build_exit_wave(attendance=attendance, random_seed=random_seed)
    return {
        "event_id": event_id,
        "attendance": attendance,
        "wave_points": len(wave),
        "wave": [p.model_dump() for p in wave],
        "data_source": "SIMULATED",
        "_fallback": True,
        "_fallback_reason": "crowd-sim-mcp unavailable; using in-process simulator",
    }


def _fallback_h3_cells(
    event_id: str,
    t_plus_minutes: int,
    attendance: int,
    venue_lat: float = 12.9789,
    venue_lon: float = 77.5996,
    random_seed: int = 42,
) -> dict:
    from app.simulator.crowd import build_exit_wave, build_h3_demand  # noqa: PLC0415
    from app.seed.constants import CHINNASWAMY_GATES  # noqa: PLC0415
    wave = build_exit_wave(attendance=attendance, random_seed=random_seed)
    cum = next(
        (p.cumulative_exited for p in wave if p.minute == t_plus_minutes),
        wave[-1].cumulative_exited,
    )
    total_demand = min(cum, attendance)
    cells = build_h3_demand(
        total_demand=total_demand,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        horizon_minutes=t_plus_minutes,
        gates=CHINNASWAMY_GATES,
        random_seed=random_seed,
    )
    peak_zone = max(cells, key=lambda c: c.demand_persons).h3_id if cells else ""
    return {
        "event_id": event_id,
        "horizon_minutes": t_plus_minutes,
        "total_demand": total_demand,
        "peak_zone_h3": peak_zone,
        "cell_count": len(cells),
        "cells": [c.model_dump() for c in cells],
        "data_source": "SIMULATED",
        "_fallback": True,
        "_fallback_reason": "crowd-sim-mcp unavailable; using in-process simulator",
    }


# ── MCP client class ──────────────────────────────────────────────────────────

class CrowdSimMCPClient:
    """
    Client for the crowd-sim-mcp Streamable HTTP MCP server.

    Usage::

        client = CrowdSimMCPClient()
        result = await client.simulate_crowd_exit(
            event_id="abc",
            t_plus_minutes=20,
            attendance=34000,
        )

    Falls back to in-process simulation if the MCP server is unreachable.
    """

    def __init__(self, url: str | None = None) -> None:
        settings = get_settings()
        self._url = url or settings.crowd_sim_mcp_url

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        """
        Call a tool on the crowd-sim-mcp MCP server via Streamable HTTP transport.

        Falls back to in-process simulator on any connection error.
        """
        try:
            from mcp.client.streamable_http import streamablehttp_client  # noqa: PLC0415
            from mcp import ClientSession  # noqa: PLC0415

            async with streamablehttp_client(self._url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    # MCP result content is a list; first item is the tool output
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, "text"):
                            import json  # noqa: PLC0415
                            return json.loads(content.text)
                    return {}
        except Exception as exc:
            log.warning(f"crowd_sim_mcp.connection_failed tool={tool_name} url={self._url} error={exc}")
            return {}  # caller handles empty dict by using fallback

    async def simulate_crowd_exit(
        self,
        event_id: str,
        t_plus_minutes: int,
        attendance: int,
        venue_lat: float = 12.9789,
        venue_lon: float = 77.5996,
        random_seed: int = 42,
    ) -> dict:
        """
        Simulate crowd exit at T+N minutes. Returns full simulation result.
        Falls back to in-process simulator if MCP server is unavailable.
        """
        result = await self._call_tool("simulate_crowd_exit", {
            "event_id": event_id,
            "t_plus_minutes": t_plus_minutes,
            "attendance": attendance,
            "venue_lat": venue_lat,
            "venue_lon": venue_lon,
            "random_seed": random_seed,
        })
        if not result:
            log.warning("crowd_sim_mcp.fallback tool=simulate_crowd_exit")
            return _fallback_simulate(
                event_id=event_id,
                t_plus_minutes=t_plus_minutes,
                attendance=attendance,
                venue_lat=venue_lat,
                venue_lon=venue_lon,
                random_seed=random_seed,
            )
        return result

    async def get_exit_wave(
        self,
        event_id: str,
        attendance: int,
        random_seed: int = 42,
    ) -> dict:
        """Return minute-by-minute exit time series. Falls back to in-process."""
        result = await self._call_tool("get_exit_wave", {
            "event_id": event_id,
            "attendance": attendance,
            "random_seed": random_seed,
        })
        if not result:
            log.warning("crowd_sim_mcp.fallback tool=get_exit_wave")
            return _fallback_exit_wave(
                event_id=event_id,
                attendance=attendance,
                random_seed=random_seed,
            )
        return result

    async def get_h3_cells_for_horizon(
        self,
        event_id: str,
        t_plus_minutes: int,
        attendance: int,
        venue_lat: float = 12.9789,
        venue_lon: float = 77.5996,
        random_seed: int = 42,
    ) -> dict:
        """Return H3 demand cells for a given horizon. Falls back to in-process."""
        result = await self._call_tool("get_h3_cells_for_horizon", {
            "event_id": event_id,
            "t_plus_minutes": t_plus_minutes,
            "attendance": attendance,
            "venue_lat": venue_lat,
            "venue_lon": venue_lon,
            "random_seed": random_seed,
        })
        if not result:
            log.warning("crowd_sim_mcp.fallback tool=get_h3_cells_for_horizon")
            return _fallback_h3_cells(
                event_id=event_id,
                t_plus_minutes=t_plus_minutes,
                attendance=attendance,
                venue_lat=venue_lat,
                venue_lon=venue_lon,
                random_seed=random_seed,
            )
        return result


# ── Module-level singleton ─────────────────────────────────────────────────────

_client: CrowdSimMCPClient | None = None


def get_crowd_sim_client() -> CrowdSimMCPClient:
    """Return the module-level CrowdSimMCPClient singleton."""
    global _client
    if _client is None:
        _client = CrowdSimMCPClient()
    return _client


def reset_client_for_testing(url: str | None = None) -> None:
    """Reset singleton — for use in tests only."""
    global _client
    _client = CrowdSimMCPClient(url=url) if url else None
