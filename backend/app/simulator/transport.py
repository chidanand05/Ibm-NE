"""
Transport supply simulation engine.

Simulates Namma Metro, BMTC buses, and auto-rickshaw availability around
M. Chinnaswamy Stadium for large events.

All values are SYNTHETIC — based on public timetable data and reasonable
assumptions. No real-time feeds are used. Every output carries
data_source="SIMULATED".

Design rules
------------
- No transport capacity can go below 0 (enforced by max(0, v))
- Metro capacity is capped at physical train limits
- Auto count decays over time as demand exceeds supply
- BMTC surge buses are assumed deployed for events > 25,000 attendance
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import h3

from app.simulator.models import (
    H3SupplyCell,
    SupplyModeResult,
    SupplySnapshot,
)

# ── Metro configuration (based on public Namma Metro timetable) ───────────────

METRO_STATIONS = [
    {
        "station_id": "mg_road",
        "name": "MG Road",
        "line": "Purple",
        "lat": 12.9752,
        "lon": 77.6060,
        "walking_minutes": 12,
        "normal_trains_per_hour": 4,
        "surge_trains_per_hour": 6,
        "capacity_per_train": 900,
        "max_platform_capacity": 1200,   # physical platform limit
    },
    {
        "station_id": "cubbon_park",
        "name": "Cubbon Park",
        "line": "Green",
        "lat": 12.9796,
        "lon": 77.5930,
        "walking_minutes": 16,
        "normal_trains_per_hour": 3,
        "surge_trains_per_hour": 4,
        "capacity_per_train": 900,
        "max_platform_capacity": 1200,
    },
]

# Physical maximum for any metro station — prevents impossible values
METRO_MAX_CAPACITY_PER_HOUR = 15_000   # persons/hour (industry ceiling for single-station)

# ── BMTC configuration (synthesized from public route data) ──────────────────

BMTC_STOPS = [
    {
        "stop_id": "kg_road",
        "name": "KG Road Junction",
        "lat": 12.9756,
        "lon": 77.5936,
        "routes": ["137", "201", "401"],
        "walking_minutes": 5,
        "normal_buses_per_hour": 3,
        "surge_buses_per_hour": 6,      # pre-positioned for events
        "capacity_per_bus": 90,          # 60 seated + 30 standing
    },
    {
        "stop_id": "mg_road_bmtc",
        "name": "MG Road Junction",
        "lat": 12.9760,
        "lon": 77.6045,
        "routes": ["36", "201"],
        "walking_minutes": 8,
        "normal_buses_per_hour": 2,
        "surge_buses_per_hour": 4,
        "capacity_per_bus": 90,
    },
]

# ── Auto-rickshaw configuration ───────────────────────────────────────────────

AUTO_BASE_COUNT = 120          # estimated within 1km radius at event end
AUTO_CAPACITY_PERSONS = 3      # standard 3-seater rickshaw
AUTO_DECAY_RATE = 0.20         # 20% reduction per 10-minute window
AUTO_TRIPS_PER_WINDOW = {       # approx trips possible in each 20-min window
    20: 2,
    40: 1,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _metro_window_capacity(station: dict, time_horizon: int, surge_active: bool) -> int:
    """
    Calculate how many persons a metro station can absorb within `time_horizon` minutes.

    Walking delay is accounted for: passengers cannot board before walk time elapses.
    """
    walk_mins = station["walking_minutes"]
    effective_window = max(0, time_horizon - walk_mins)
    if effective_window <= 0:
        return 0

    tph = station["surge_trains_per_hour"] if surge_active else station["normal_trains_per_hour"]
    cap = station["capacity_per_train"]

    # Trains available within effective_window minutes
    trains_in_window = (effective_window / 60.0) * tph
    raw_capacity = int(trains_in_window * cap)

    # Cap at physical maximum
    max_cap = int((time_horizon / 60.0) * METRO_MAX_CAPACITY_PER_HOUR)
    return max(0, min(raw_capacity, max_cap))


def _bmtc_window_capacity(stop: dict, time_horizon: int, surge_active: bool) -> int:
    """Buses within `time_horizon` minutes, accounting for walking time."""
    walk_mins = stop["walking_minutes"]
    effective_window = max(0, time_horizon - walk_mins)
    if effective_window <= 0:
        return 0

    bph = stop["surge_buses_per_hour"] if surge_active else stop["normal_buses_per_hour"]
    buses_in_window = (effective_window / 60.0) * bph
    return max(0, int(buses_in_window * stop["capacity_per_bus"]))


def _auto_available(time_horizon: int, base_count: int = AUTO_BASE_COUNT) -> int:
    """
    Auto count decreases over time as demand absorbs available vehicles.
    Uses integer decay: 20% per 10-minute window, floored at 0.
    """
    periods = time_horizon // 10  # number of 10-min windows elapsed
    count = base_count
    for _ in range(periods):
        count = max(0, count - int(count * AUTO_DECAY_RATE))
    return max(0, count)


def _auto_window_capacity(time_horizon: int, base_count: int = AUTO_BASE_COUNT) -> int:
    """
    Total persons auto-rickshaws can move in the time_horizon window.
    = available_count × persons_per_auto × trips_possible
    """
    available = _auto_available(time_horizon, base_count)
    trips = AUTO_TRIPS_PER_WINDOW.get(time_horizon, max(1, time_horizon // 20))
    return max(0, available * AUTO_CAPACITY_PERSONS * trips)


# ── Supply-demand gap ─────────────────────────────────────────────────────────

def _compute_gap(demand: int, supply: int) -> int:
    """Positive = shortage, negative = surplus."""
    return demand - supply


# ── H3 supply map ─────────────────────────────────────────────────────────────

def _build_h3_supply_map(
    venue_lat: float,
    venue_lon: float,
    modes: list[SupplyModeResult],
    resolution: int = 7,
) -> list[H3SupplyCell]:
    """
    Map supply capacity to H3 cells near each station/stop.
    Simple approach: assign the mode's window_capacity to the H3 cell
    containing the corresponding station.
    """
    cells: list[H3SupplyCell] = []

    # Metro stations
    for station in METRO_STATIONS:
        h3_id = h3.latlng_to_cell(station["lat"], station["lon"], resolution)
        # Find matching metro mode result
        metro_mode = next((m for m in modes if m.mode == "METRO"), None)
        if metro_mode:
            # Distribute equally across stations
            per_station_cap = max(0, metro_mode.window_capacity // len(METRO_STATIONS))
            cells.append(H3SupplyCell(h3_id=h3_id, mode="METRO", capacity_persons=per_station_cap))

    # BMTC stops
    for stop in BMTC_STOPS:
        h3_id = h3.latlng_to_cell(stop["lat"], stop["lon"], resolution)
        bmtc_mode = next((m for m in modes if m.mode == "BMTC"), None)
        if bmtc_mode:
            per_stop_cap = max(0, bmtc_mode.window_capacity // len(BMTC_STOPS))
            cells.append(H3SupplyCell(h3_id=h3_id, mode="BMTC", capacity_persons=per_stop_cap))

    # Auto — near venue center
    auto_mode = next((m for m in modes if m.mode == "AUTO"), None)
    if auto_mode:
        venue_h3 = h3.latlng_to_cell(venue_lat, venue_lon, resolution)
        cells.append(H3SupplyCell(h3_id=venue_h3, mode="AUTO", capacity_persons=auto_mode.window_capacity))

    return cells


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
) -> SupplySnapshot:
    """
    Compute transport supply snapshot at `time_horizon` minutes after event end.

    Parameters
    ----------
    event_id        Event identifier.
    time_horizon    Minutes from event end (typically 20 or 40).
    total_demand    Total persons needing transport (from CrowdSimulationResult.total_demand).
    venue_lat/lon   Venue centre.
    attendance      Full event attendance (used for surge threshold).
    surge_active    Whether Metro/BMTC surge services are deployed.
    auto_base_count Starting auto-rickshaw count within 1km.

    Returns
    -------
    SupplySnapshot — fully validated Pydantic model.
    """
    # ── Metro ─────────────────────────────────────────────────────────────────
    metro_window_cap = sum(
        _metro_window_capacity(s, time_horizon, surge_active) for s in METRO_STATIONS
    )
    metro_cap_per_hour = sum(
        (
            s["surge_trains_per_hour"] if surge_active else s["normal_trains_per_hour"]
        ) * s["capacity_per_train"]
        for s in METRO_STATIONS
    )
    metro_mode = SupplyModeResult(
        mode="METRO",
        capacity_per_hour=min(metro_cap_per_hour, METRO_MAX_CAPACITY_PER_HOUR),
        vehicles_available=sum(
            s["surge_trains_per_hour"] if surge_active else s["normal_trains_per_hour"]
            for s in METRO_STATIONS
        ),
        frequency_minutes=max(
            1,
            round(60 / (METRO_STATIONS[0]["surge_trains_per_hour"] if surge_active else METRO_STATIONS[0]["normal_trains_per_hour"]))
        ),
        operational=True,
        window_capacity=metro_window_cap,
        gap_persons=_compute_gap(total_demand, metro_window_cap),
        notes=(
            "Namma Metro Purple + Green lines. Walking time to nearest station "
            "12–16 min accounted for. Data source: public timetable + simulated surge."
        ),
        data_source="SIMULATED",
    )

    # ── BMTC ─────────────────────────────────────────────────────────────────
    bmtc_surge = surge_active and attendance >= 25_000
    bmtc_window_cap = sum(_bmtc_window_capacity(s, time_horizon, bmtc_surge) for s in BMTC_STOPS)
    bmtc_total_buses = sum(
        s["surge_buses_per_hour"] if bmtc_surge else s["normal_buses_per_hour"]
        for s in BMTC_STOPS
    )
    bmtc_cap_per_hour = bmtc_total_buses * BMTC_STOPS[0]["capacity_per_bus"]
    bmtc_mode = SupplyModeResult(
        mode="BMTC",
        capacity_per_hour=bmtc_cap_per_hour,
        vehicles_available=bmtc_total_buses,
        frequency_minutes=max(1, 60 // max(1, bmtc_total_buses)),
        operational=True,
        window_capacity=bmtc_window_cap,
        gap_persons=_compute_gap(total_demand, bmtc_window_cap),
        notes=(
            "BMTC stops at KG Road and MG Road. Surge buses pre-positioned for large events. "
            "Counts are SIMULATED — no real-time BMTC API."
        ),
        data_source="SIMULATED",
    )

    # ── Auto-rickshaw ─────────────────────────────────────────────────────────
    auto_window_cap = _auto_window_capacity(time_horizon, auto_base_count)
    auto_available = _auto_available(time_horizon, auto_base_count)
    auto_mode = SupplyModeResult(
        mode="AUTO",
        capacity_per_hour=max(0, auto_available * AUTO_CAPACITY_PERSONS * 3),  # ~3 trips/hr
        vehicles_available=auto_available,
        frequency_minutes=None,   # on-demand
        operational=True,
        window_capacity=auto_window_cap,
        gap_persons=_compute_gap(total_demand, auto_window_cap),
        notes=(
            f"Auto count decays from {auto_base_count} base. "
            "SIMULATED — no real-time GPS or app data used."
        ),
        data_source="SIMULATED",
    )

    modes = [metro_mode, bmtc_mode, auto_mode]
    total_window_cap = sum(m.window_capacity for m in modes)

    h3_supply_map = _build_h3_supply_map(venue_lat, venue_lon, modes)

    return SupplySnapshot(
        event_id=event_id,
        time_horizon=time_horizon,
        modes=modes,
        total_window_capacity=total_window_cap,
        overall_gap=_compute_gap(total_demand, total_window_cap),
        h3_supply_map=h3_supply_map,
        data_source_summary=(
            "All transport data is SIMULATED. "
            "Metro schedule based on public timetables with simulated surge. "
            "BMTC and auto counts are synthetic estimates — no real-time GPS data used."
        ),
        data_source="SIMULATED",
        simulated_at=datetime.now(tz=timezone.utc),
    )
