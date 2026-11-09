"""
MCP Server 5 — Transport Supply Server (in-process).

Wraps backend/app/simulator/transport.py.
No simulation logic is duplicated here — this module is a thin
MCP-compatible adapter over the existing simulator functions.

Promotion path: wrap each function in @mcp.tool() for Streamable HTTP MCP.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.simulator.transport import (
    AUTO_BASE_COUNT,
    _auto_available,
    _auto_window_capacity,
    get_supply_snapshot as _get_supply_snapshot,
)


# ── Public API ────────────────────────────────────────────────────────────────

def get_supply_snapshot(
    event_id: str,
    time_horizon: int,
    total_demand: int,
    venue_lat: float,
    venue_lon: float,
    attendance: int,
    surge_active: bool = True,
    auto_base_count: int = AUTO_BASE_COUNT,
) -> dict:
    """
    Return transport supply snapshot at `time_horizon` minutes after event end.

    Delegates to simulator/transport.py. Output is serialized to a dict
    for MCP tool compatibility.

    Parameters
    ----------
    event_id        Unique event identifier.
    time_horizon    Minutes from event end (typically 20 or 40).
    total_demand    Total persons needing transport (from crowd simulation).
    venue_lat/lon   Venue centre coordinates.
    attendance      Full event attendance.
    surge_active    Whether Metro/BMTC surge services are deployed.
    auto_base_count Starting auto-rickshaw count estimate.

    Returns
    -------
    Dict matching SupplySnapshot schema with all data_source fields set to "SIMULATED".
    """
    snapshot = _get_supply_snapshot(
        event_id=event_id,
        time_horizon=time_horizon,
        total_demand=total_demand,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        attendance=attendance,
        surge_active=surge_active,
        auto_base_count=auto_base_count,
    )
    return snapshot.model_dump()


def identify_supply_gaps(
    demand_forecast: dict,
    supply_snapshot: dict,
) -> dict:
    """
    Identify transport supply-demand gaps from forecast and supply data.

    Parameters
    ----------
    demand_forecast   EgressForecastOutput-compatible dict with:
                        total_demand_20min, total_demand_40min (or total_demand)
    supply_snapshot   SupplySnapshot-compatible dict with:
                        time_horizon, total_window_capacity, modes list

    Returns
    -------
    Gap analysis dict with overall_gap, per_mode_gaps, critical_gaps list,
    and adequacy_rating.
    """
    # Extract demand — support both naming conventions
    demand = (
        demand_forecast.get("total_demand")
        or demand_forecast.get(f"total_demand_{supply_snapshot.get('time_horizon', 20)}min")
        or 0
    )
    total_supply = supply_snapshot.get("total_window_capacity", 0)
    overall_gap = demand - total_supply

    # Per-mode gaps
    per_mode_gaps = []
    critical_gaps: list[str] = []

    for mode in supply_snapshot.get("modes", []):
        mode_name = mode.get("mode", "UNKNOWN")
        mode_supply = mode.get("window_capacity", 0)
        mode_gap = demand - mode_supply   # demand vs single mode (informational)
        per_mode_gaps.append({
            "mode": mode_name,
            "window_capacity": mode_supply,
            "gap_vs_total_demand": mode_gap,
            "data_source": "SIMULATED",
        })

    # Critical gaps: overall shortage > 5,000 persons
    if overall_gap > 5_000:
        critical_gaps.append(
            f"Overall transport shortage: {overall_gap:,} persons have no transport at "
            f"T+{supply_snapshot.get('time_horizon', '?')} minutes"
        )

    # Metro-specific gap
    metro_mode = next((m for m in supply_snapshot.get("modes", []) if m.get("mode") == "METRO"), None)
    if metro_mode and metro_mode.get("window_capacity", 0) < demand * 0.3:
        critical_gaps.append(
            f"Metro covers only {metro_mode.get('window_capacity', 0):,} of "
            f"{demand:,} persons — insufficient for primary transport demand"
        )

    # Adequacy rating
    if overall_gap <= 0:
        adequacy = "ADEQUATE"
    elif overall_gap <= 3_000:
        adequacy = "MINOR_SHORTAGE"
    elif overall_gap <= 10_000:
        adequacy = "MODERATE_SHORTAGE"
    else:
        adequacy = "CRITICAL_SHORTAGE"

    return {
        "event_id": demand_forecast.get("event_id", supply_snapshot.get("event_id", "")),
        "time_horizon": supply_snapshot.get("time_horizon", 20),
        "total_demand": demand,
        "total_supply": total_supply,
        "overall_gap": overall_gap,
        "per_mode_gaps": per_mode_gaps,
        "critical_gaps": critical_gaps,
        "adequacy_rating": adequacy,
        "data_source": "SIMULATED",
        "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def get_auto_availability(
    h3_id: str,
    time_horizon: int,
    base_count: int = AUTO_BASE_COUNT,
) -> dict:
    """
    Return simulated auto-rickshaw availability for a given H3 cell and time horizon.

    Auto count decays from base_count as demand absorbs available vehicles.

    Parameters
    ----------
    h3_id         H3 cell ID (stored for reference — no spatial lookup performed).
    time_horizon  Minutes from event end.
    base_count    Starting auto count in the area (default 120).

    Returns
    -------
    Dict with available_count, capacity_persons, window_capacity, time_horizon, data_source.
    """
    available = _auto_available(time_horizon, base_count)
    window_cap = _auto_window_capacity(time_horizon, base_count)

    return {
        "h3_id": h3_id,
        "time_horizon": time_horizon,
        "available_count": available,
        "capacity_per_auto": 3,
        "window_capacity": window_cap,
        "base_count": base_count,
        "note": (
            "Auto availability is SIMULATED using a 20%/10-min decay model. "
            "No real-time GPS or app data is used."
        ),
        "data_source": "SIMULATED",
    }
