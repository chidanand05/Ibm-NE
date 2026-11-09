"""
MCP tool permission enforcement.

All agent-to-tool authorization checks go through check_permission().
Permissions are defined statically — they never change at runtime.

Permission format
-----------------
"server_name.*"          → all tools on that server
"server_name.tool_name"  → exactly that one tool

call_tool() in base_agent (M3) calls check_permission() BEFORE invoking
the tool function, so the tool modules themselves are not permission-aware.

Source of truth: docs/agent-contracts.md § Agent Permission Matrix
"""

from __future__ import annotations

# ── Permission table ──────────────────────────────────────────────────────────

AGENT_PERMISSIONS: dict[str, list[str]] = {
    "event_intelligence": [
        "event_server.get_event_details",
        "event_server.list_upcoming_events",
        "event_server.get_venue_layout",
        "history_server.retrieve_similar_events",
    ],
    "egress_forecast": [
        "simulation_server.simulate_crowd_exit",
        "simulation_server.simulate_exit_wave",
        "simulation_server.get_stadium_gate_flow",
        "h3_server.*",
    ],
    "supply": [
        "transit_server.get_metro_departures",
        "transit_server.get_bmtc_routes_near",
        "transit_server.get_metro_capacity",
        "supply_server.get_supply_snapshot",
        "supply_server.identify_supply_gaps",
        "supply_server.get_auto_availability",
    ],
    "police_coordination": [
        "h3_server.*",
        "simulation_server.simulate_crowd_exit",
        "event_server.get_venue_layout",
    ],
    "planner": [
        "history_server.retrieve_similar_events",
        "history_server.get_event_outcome",
        "event_server.get_event_details",
    ],
    "citizen_guidance": [
        "transit_server.get_metro_departures",
        "transit_server.get_bmtc_routes_near",
        "event_server.get_venue_layout",
    ],
    "learning": [
        "history_server.store_event_outcome",
        "history_server.retrieve_similar_events",
        "simulation_server.simulate_crowd_exit",
    ],
}

# All known agent IDs — used for validation
ALL_AGENT_IDS: frozenset[str] = frozenset(AGENT_PERMISSIONS.keys())


# ── Error type ────────────────────────────────────────────────────────────────

class PermissionDeniedError(PermissionError):
    """Raised when an agent attempts to call a tool it is not authorized for."""

    def __init__(self, agent_id: str, tool_name: str) -> None:
        self.agent_id = agent_id
        self.tool_name = tool_name
        super().__init__(
            f"Agent '{agent_id}' is not authorized to call '{tool_name}'. "
            f"Allowed tools: {AGENT_PERMISSIONS.get(agent_id, [])}"
        )


# ── Authorization logic ───────────────────────────────────────────────────────

def _is_authorized(agent_id: str, tool_name: str) -> bool:
    """
    Return True if agent_id is permitted to call tool_name.

    tool_name must be in "server.tool" format, e.g. "h3_server.latlon_to_h3".
    Wildcard entries like "h3_server.*" grant access to all tools on that server.
    """
    allowed = AGENT_PERMISSIONS.get(agent_id, [])
    if not allowed:
        return False

    # Split tool_name into server + tool parts
    parts = tool_name.split(".", 1)
    server = parts[0] if len(parts) == 2 else tool_name

    for entry in allowed:
        # Exact match
        if entry == tool_name:
            return True
        # Wildcard match: "server.*"
        if entry.endswith(".*") and entry[:-2] == server:
            return True

    return False


def check_permission(agent_id: str, tool_name: str) -> None:
    """
    Raise PermissionDeniedError if agent_id cannot call tool_name.

    Parameters
    ----------
    agent_id   One of the 7 agent IDs (e.g. "supply", "planner").
    tool_name  Fully-qualified tool name (e.g. "h3_server.latlon_to_h3").

    Raises
    ------
    PermissionDeniedError  If the agent is not authorized.
    ValueError             If agent_id is completely unknown.
    """
    if agent_id not in ALL_AGENT_IDS:
        raise ValueError(
            f"Unknown agent_id '{agent_id}'. "
            f"Known agents: {sorted(ALL_AGENT_IDS)}"
        )
    if not _is_authorized(agent_id, tool_name):
        raise PermissionDeniedError(agent_id, tool_name)
