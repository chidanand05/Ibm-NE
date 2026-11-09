"""
Traffic congestion simulation around M. Chinnaswamy Stadium.

Models road congestion on five key corridors based on observed patterns at
large cricket matches. All values are SYNTHETIC — no real-time traffic feeds.

Every output carries data_source="SIMULATED".
"""

from __future__ import annotations

from datetime import datetime, timezone

import h3

from app.simulator.models import (
    CongestionLevel,
    CongestionPoint,
    TrafficSimulationResult,
)

# ── Road segment definitions ──────────────────────────────────────────────────
# Positions are representative points on each road segment, not exact junctions.

ROAD_SEGMENTS = [
    {
        "name": "MG Road (Vidhana Soudha to Ulsoor)",
        "lat": 12.9756,
        "lon": 77.6013,
        # Congestion profile: (minute_start, minute_end, level)
        # Pattern: builds quickly after event, peaks mid-egress, subsides later
        "congestion_profile": [
            (0,  10,  "LOW"),
            (10, 30,  "HIGH"),
            (30, 45,  "MEDIUM"),
            (45, 60,  "LOW"),
        ],
        "peak_minute": 20,
        "recommended_diversion": "Use Kasturba Road or Cubbon Road via Vidhana Soudha",
    },
    {
        "name": "Cubbon Road (Queen's Circle junction)",
        "lat": 12.9769,
        "lon": 77.5939,
        "congestion_profile": [
            (0,  12,  "LOW"),
            (12, 28,  "MEDIUM"),
            (28, 42,  "LOW"),
            (42, 60,  "CLEAR"),
        ],
        "peak_minute": 18,
        "recommended_diversion": "Use Raj Bhavan Road toward Palace Road",
    },
    {
        "name": "Kasturba Road (toward MG Road Metro)",
        "lat": 12.9787,
        "lon": 77.5970,
        "congestion_profile": [
            (0,  8,   "MEDIUM"),
            (8,  25,  "HIGH"),
            (25, 38,  "MEDIUM"),
            (38, 60,  "LOW"),
        ],
        "peak_minute": 15,
        "recommended_diversion": "Approach MG Road Metro from Cubbon Road side",
    },
    {
        "name": "Vittal Mallya Road",
        "lat": 12.9717,
        "lon": 77.5969,
        "congestion_profile": [
            (0,  15,  "LOW"),
            (15, 30,  "MEDIUM"),
            (30, 45,  "LOW"),
            (45, 60,  "CLEAR"),
        ],
        "peak_minute": 22,
        "recommended_diversion": "Continue to Lavelle Road for alternate exit",
    },
    {
        "name": "Residency Road (alternate corridor)",
        "lat": 12.9730,
        "lon": 77.6010,
        "congestion_profile": [
            (0,  20,  "LOW"),
            (20, 35,  "LOW"),
            (35, 60,  "CLEAR"),
        ],
        "peak_minute": 25,
        "recommended_diversion": "Preferred alternate route — use when MG Road is HIGH",
    },
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _level_at_minute(profile: list[tuple[int, int, str]], minute: int) -> str:
    """Return congestion level at the given minute from the profile."""
    for start, end, level in profile:
        if start <= minute < end:
            return level
    # After last profile window — CLEAR
    return "CLEAR"


def _congested_minutes(profile: list[tuple[int, int, str]], max_minute: int = 60) -> list[int]:
    """Return list of minutes where congestion is MEDIUM or worse."""
    congested = []
    for m in range(max_minute + 1):
        level = _level_at_minute(profile, m)
        if level in ("MEDIUM", "HIGH", "CRITICAL"):
            congested.append(m)
    return congested


def _worst_level(profile: list[tuple[int, int, str]]) -> CongestionLevel:  # type: ignore[return]
    """Return the worst congestion level across all time windows."""
    order: dict[str, int] = {"CLEAR": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    worst = "CLEAR"
    for _, _, level in profile:
        if order.get(level, 0) > order.get(worst, 0):
            worst = level
    return worst  # type: ignore[return-value]


# ── Public API ────────────────────────────────────────────────────────────────

def simulate_congestion(
    event_id: str,
    horizon_minutes: int = 60,
    resolution: int = 8,   # resolution 8 gives finer cells for road-level precision
) -> TrafficSimulationResult:
    """
    Simulate traffic congestion around Chinnaswamy Stadium.

    Parameters
    ----------
    event_id         Event identifier.
    horizon_minutes  Time window to simulate (default 60 minutes).
    resolution       H3 resolution for road segment cells (default 8 — finer than demand cells).

    Returns
    -------
    TrafficSimulationResult — validated Pydantic model with congestion points.
    """
    congestion_points: list[CongestionPoint] = []
    critical_roads: list[str] = []

    for segment in ROAD_SEGMENTS:
        profile: list[tuple[int, int, str]] = segment["congestion_profile"]  # type: ignore[assignment]
        worst: CongestionLevel = _worst_level(profile)  # type: ignore[assignment]
        h3_id = h3.latlng_to_cell(segment["lat"], segment["lon"], resolution)

        congested_minutes_list = _congested_minutes(profile, max_minute=min(horizon_minutes, 60))

        point = CongestionPoint(
            name=segment["name"],
            h3_id=h3_id,
            lat=segment["lat"],
            lon=segment["lon"],
            congestion_level=worst,
            peak_minute=segment["peak_minute"],
            congestion_minutes=congested_minutes_list,
            recommended_diversion=segment.get("recommended_diversion", ""),
            data_source="SIMULATED",
        )
        congestion_points.append(point)

        if worst in ("HIGH", "CRITICAL"):
            critical_roads.append(segment["name"])

    return TrafficSimulationResult(
        event_id=event_id,
        horizon_minutes=horizon_minutes,
        congestion_points=congestion_points,
        critical_roads=critical_roads,
        data_source="SIMULATED",
        simulated_at=datetime.now(tz=timezone.utc),
    )
