"""
Crowd Simulation MCP Server — Sub-task 2.3a.

Standalone Streamable HTTP MCP server using MCP SDK v2 (MCPServer).
Runs as Docker service crowd-sim-mcp on port 8001 (internal network only).

Architecture note:
- This server is MCP-only — it does NOT expose REST endpoints.
- The backend accesses it via HTTP MCP protocol at http://crowd-sim-mcp:8001/mcp
- All simulation data is SYNTHETIC — labeled as data_source="SIMULATED" in every response.
- No LLM calls anywhere in this server.
- No database connections in this server.

Agent permissions:
- crowd_sim: simulate_crowd_exit, get_exit_wave, get_h3_cells
- (permissions enforced by backend before calling this server)

MCP tools registered:
1. simulate_crowd_exit    — Full simulation result at T+N
2. get_exit_wave          — Minute-by-minute exit time series
3. get_h3_cells_for_horizon — H3 hex demand at T+N
"""

from __future__ import annotations

import os
import logging
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from crowd_logic import (
    simulate_crowd_exit as _simulate,
    get_exit_wave as _get_wave,
    get_h3_cells as _get_h3,
    CHINNASWAMY_GATES_DEFAULT,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crowd-sim-mcp")

# ── Create MCP server ─────────────────────────────────────────────────────────

mcp = MCPServer(
    "crowd-sim-mcp",
    instructions=(
        "Crowd simulation MCP server for Namma Exodus. "
        "ALL data returned is SIMULATED and must be treated as synthetic. "
        "Never present simulated results as real crowd data."
    ),
)


# ── Tool 1: simulate_crowd_exit ───────────────────────────────────────────────

@mcp.tool()
def simulate_crowd_exit(
    event_id: Annotated[str, Field(description="Event identifier string")],
    t_plus_minutes: Annotated[int, Field(description="Minutes after event end: 20 or 40", ge=1, le=120)],
    attendance: Annotated[int, Field(description="Expected total attendance", ge=1000, le=100000)],
    venue_lat: Annotated[float, Field(description="Venue latitude (degrees)", ge=-90.0, le=90.0)] = 12.9789,
    venue_lon: Annotated[float, Field(description="Venue longitude (degrees)", ge=-180.0, le=180.0)] = 77.5996,
    random_seed: Annotated[int, Field(description="Seed for reproducible results", ge=0)] = 42,
) -> dict:
    """
    Simulate crowd exit demand at T+N minutes after event end.

    Returns full simulation result including H3 demand cells, exit wave,
    gate flows, and summary statistics.

    ALL DATA IS SIMULATED — data_source='SIMULATED' in all outputs.
    """
    log.info(
        "simulate_crowd_exit called",
        extra={"event_id": event_id, "t_plus": t_plus_minutes, "attendance": attendance},
    )
    result = _simulate(
        event_id=event_id,
        t_plus_minutes=t_plus_minutes,
        attendance=attendance,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        gates=CHINNASWAMY_GATES_DEFAULT,
        random_seed=random_seed,
    )
    return result


# ── Tool 2: get_exit_wave ─────────────────────────────────────────────────────

@mcp.tool()
def get_exit_wave(
    event_id: Annotated[str, Field(description="Event identifier string")],
    attendance: Annotated[int, Field(description="Expected total attendance", ge=1000, le=100000)],
    random_seed: Annotated[int, Field(description="Seed for reproducible results", ge=0)] = 42,
) -> dict:
    """
    Return minute-by-minute crowd exit time series (0–60 minutes after event end).

    Useful for visualising the exit curve shape and identifying peak exit minutes.
    ALL DATA IS SIMULATED.
    """
    log.info("get_exit_wave called", extra={"event_id": event_id, "attendance": attendance})
    return _get_wave(
        event_id=event_id,
        attendance=attendance,
        random_seed=random_seed,
    )


# ── Tool 3: get_h3_cells_for_horizon ─────────────────────────────────────────

@mcp.tool()
def get_h3_cells_for_horizon(
    event_id: Annotated[str, Field(description="Event identifier string")],
    t_plus_minutes: Annotated[int, Field(description="Minutes after event end: 20 or 40", ge=1, le=120)],
    attendance: Annotated[int, Field(description="Expected total attendance", ge=1000, le=100000)],
    venue_lat: Annotated[float, Field(description="Venue latitude (degrees)", ge=-90.0, le=90.0)] = 12.9789,
    venue_lon: Annotated[float, Field(description="Venue longitude (degrees)", ge=-180.0, le=180.0)] = 77.5996,
    random_seed: Annotated[int, Field(description="Seed for reproducible results", ge=0)] = 42,
) -> dict:
    """
    Return H3 hexagonal demand cells for a given time horizon.

    Returns cell demand_persons, demand_category (LOW/MEDIUM/HIGH/CRITICAL),
    and center coordinates for each H3 cell in the venue vicinity.
    ALL DATA IS SIMULATED.
    """
    log.info(
        "get_h3_cells_for_horizon called",
        extra={"event_id": event_id, "t_plus": t_plus_minutes, "attendance": attendance},
    )
    return _get_h3(
        event_id=event_id,
        t_plus_minutes=t_plus_minutes,
        attendance=attendance,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        gates=CHINNASWAMY_GATES_DEFAULT,
        random_seed=random_seed,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8001"))
    log.info(f"Starting crowd-sim-mcp on {host}:{port}/mcp")
    mcp.run_streamable_http_async(host=host, port=port, streamable_http_path="/mcp")
