"""
Crowd Simulation MCP Server — crowd_logic.py

Pure Python crowd simulation logic for the standalone crowd-sim-mcp service.
This module is a self-contained copy so the MCP server has NO dependency on
the backend app package. Reuses the same physics model as backend/app/simulator/.

All outputs carry data_source="SIMULATED".
No LLM calls anywhere in this module.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

# ── Constants (mirrors backend/app/simulator/crowd.py) ───────────────────────

CONFIDENCE_SIMULATED = 0.82
H3_RESOLUTION = 7
GRID_DISK_K = 3

DEMAND_THRESHOLDS: dict[str, int] = {
    "CRITICAL": 3000,
    "HIGH": 1500,
    "MEDIUM": 500,
}

METRO_ATTRACTION_POINTS = [
    {"lat": 12.9752, "lon": 77.6060, "weight": 0.25},
    {"lat": 12.9796, "lon": 77.5930, "weight": 0.18},
]

CHINNASWAMY_GATES_DEFAULT = [
    {"gate_id": "A", "name": "North Gate",  "lat": 12.9800, "lon": 77.5990, "capacity_pct": 0.25},
    {"gate_id": "B", "name": "South Gate",  "lat": 12.9778, "lon": 77.5996, "capacity_pct": 0.25},
    {"gate_id": "C", "name": "East Gate",   "lat": 12.9789, "lon": 77.6008, "capacity_pct": 0.20},
    {"gate_id": "D", "name": "West Gate",   "lat": 12.9789, "lon": 77.5984, "capacity_pct": 0.20},
    {"gate_id": "E", "name": "VIP Gate",    "lat": 12.9795, "lon": 77.5992, "capacity_pct": 0.10},
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _demand_category(persons: int) -> str:
    if persons >= DEMAND_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if persons >= DEMAND_THRESHOLDS["HIGH"]:
        return "HIGH"
    if persons >= DEMAND_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _lcg_noise(seed: int, index: int, amplitude: float = 0.08) -> float:
    val = (seed * 1664525 + 1013904223 + index * 22695477) & 0xFFFFFFFF
    return (val / 0xFFFFFFFF - 0.5) * 2 * amplitude


def _normal_pdf(x: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


# ── Exit wave ─────────────────────────────────────────────────────────────────

def build_exit_wave(
    attendance: int,
    peak_minute: int = 15,
    wave_sigma: float = 12.0,
    max_minute: int = 60,
    random_seed: int = 42,
) -> list[dict]:
    early_crowd = int(attendance * 0.75)
    patient_crowd = attendance - early_crowd
    minutes = list(range(max_minute + 1))

    early_weights = [_normal_pdf(m, peak_minute, wave_sigma) for m in minutes]
    w_sum = sum(early_weights) or 1.0
    early_raw = [early_crowd * w / w_sum for w in early_weights]

    patient_span = max(1, max_minute - peak_minute + 1)
    patient_per_minute = patient_crowd / patient_span
    patient_raw = [patient_per_minute if m >= peak_minute else 0.0 for m in minutes]

    combined = [e + p for e, p in zip(early_raw, patient_raw)]
    noisy = [max(0.0, v * (1 + _lcg_noise(random_seed, i, 0.05))) for i, v in enumerate(combined)]

    total = sum(noisy) or 1.0
    scaled = [v / total * attendance for v in noisy]
    rounded = [max(0, round(v)) for v in scaled]
    diff = attendance - sum(rounded)
    peak_idx = max(range(len(rounded)), key=lambda i: rounded[i])
    rounded[peak_idx] = max(0, rounded[peak_idx] + diff)

    wave = []
    cumulative = 0
    for minute, exiting in enumerate(rounded):
        cumulative += exiting
        wave.append({
            "minute": minute,
            "persons_exiting": exiting,
            "cumulative_exited": cumulative,
            "remaining_in_venue": max(0, attendance - cumulative),
            "data_source": "SIMULATED",
        })
    return wave


# ── H3 demand ─────────────────────────────────────────────────────────────────

def build_h3_demand(
    total_demand: int,
    venue_lat: float,
    venue_lon: float,
    horizon_minutes: int,
    gates: list[dict[str, Any]],
    random_seed: int = 42,
) -> list[dict]:
    import h3
    center_h3 = h3.latlng_to_cell(venue_lat, venue_lon, H3_RESOLUTION)
    cell_ids: list[str] = list(h3.grid_disk(center_h3, GRID_DISK_K))
    if not cell_ids:
        cell_ids = [center_h3]

    n_gates = len(gates)
    raw_fracs = []
    for i, gate in enumerate(gates):
        base = float(gate.get("capacity_pct", 1.0 / max(n_gates, 1)))
        raw_fracs.append(max(0.0, base + _lcg_noise(random_seed + 1000, i, 0.03)))
    total_f = sum(raw_fracs) or 1.0
    gate_fracs = [f / total_f for f in raw_fracs]

    weights: list[float] = []
    for idx, cell_id in enumerate(cell_ids):
        clat, clon = h3.cell_to_latlng(cell_id)
        gate_w = sum(
            frac / max(0.1, _haversine_km(clat, clon, float(g["lat"]), float(g["lon"])) ** 2)
            for g, frac in zip(gates, gate_fracs)
        )
        metro_w = sum(
            mp["weight"] / max(0.1, _haversine_km(clat, clon, mp["lat"], mp["lon"]) ** 2)
            for mp in METRO_ATTRACTION_POINTS
        )
        noise = 1.0 + _lcg_noise(random_seed + 2000, idx, 0.08)
        weights.append(max(0.0, (gate_w + metro_w * 0.4) * noise))

    w_total = sum(weights) or 1.0
    raw_demand = [total_demand * w / w_total for w in weights]
    demands = [max(0, round(v)) for v in raw_demand]
    residual = total_demand - sum(demands)
    if residual != 0:
        peak_idx = max(range(len(weights)), key=lambda i: weights[i])
        demands[peak_idx] = max(0, demands[peak_idx] + residual)

    results = []
    for cell_id, demand in zip(cell_ids, demands):
        clat, clon = h3.cell_to_latlng(cell_id)
        results.append({
            "h3_id": cell_id,
            "resolution": H3_RESOLUTION,
            "center_lat": round(clat, 6),
            "center_lon": round(clon, 6),
            "demand_persons": demand,
            "demand_category": _demand_category(demand),
            "horizon_minutes": horizon_minutes,
            "data_source": "SIMULATED",
        })
    return results


# ── Public simulation functions ───────────────────────────────────────────────

def simulate_crowd_exit(
    event_id: str,
    t_plus_minutes: int,
    attendance: int,
    venue_lat: float = 12.9789,
    venue_lon: float = 77.5996,
    gates: list[dict[str, Any]] | None = None,
    random_seed: int = 42,
) -> dict:
    """
    Simulate crowd-exit demand at T+N minutes after event end.
    Returns a plain dict (not Pydantic) — suitable for JSON serialization.
    All values are deterministic for the same inputs.
    """
    if gates is None:
        gates = CHINNASWAMY_GATES_DEFAULT

    wave = build_exit_wave(attendance=attendance, random_seed=random_seed)

    cum_at_horizon = next(
        (p["cumulative_exited"] for p in wave if p["minute"] == t_plus_minutes),
        wave[-1]["cumulative_exited"],
    )
    remaining_at_horizon = next(
        (p["remaining_in_venue"] for p in wave if p["minute"] == t_plus_minutes),
        0,
    )
    total_demand = min(cum_at_horizon, attendance)

    h3_cells = build_h3_demand(
        total_demand=total_demand,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        horizon_minutes=t_plus_minutes,
        gates=gates,
        random_seed=random_seed,
    )

    peak_zone = max(h3_cells, key=lambda c: c["demand_persons"])["h3_id"] if h3_cells else ""

    return {
        "event_id": event_id,
        "attendance": attendance,
        "horizon_minutes": t_plus_minutes,
        "total_demand": total_demand,
        "remaining_in_venue": remaining_at_horizon,
        "peak_zone_h3": peak_zone,
        "h3_cell_count": len(h3_cells),
        "h3_cells": h3_cells,
        "exit_wave": wave,
        "confidence": CONFIDENCE_SIMULATED,
        "data_source": "SIMULATED",
        "simulated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def get_exit_wave(
    event_id: str,
    attendance: int,
    random_seed: int = 42,
) -> dict:
    """Return just the exit wave time series for an event."""
    wave = build_exit_wave(attendance=attendance, random_seed=random_seed)
    return {
        "event_id": event_id,
        "attendance": attendance,
        "wave_points": len(wave),
        "wave": wave,
        "data_source": "SIMULATED",
    }


def get_h3_cells(
    event_id: str,
    t_plus_minutes: int,
    attendance: int,
    venue_lat: float = 12.9789,
    venue_lon: float = 77.5996,
    gates: list[dict[str, Any]] | None = None,
    random_seed: int = 42,
) -> dict:
    """Return H3 demand cells without the full exit wave."""
    if gates is None:
        gates = CHINNASWAMY_GATES_DEFAULT

    wave = build_exit_wave(attendance=attendance, random_seed=random_seed)
    cum_at_horizon = next(
        (p["cumulative_exited"] for p in wave if p["minute"] == t_plus_minutes),
        wave[-1]["cumulative_exited"],
    )
    total_demand = min(cum_at_horizon, attendance)

    cells = build_h3_demand(
        total_demand=total_demand,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        horizon_minutes=t_plus_minutes,
        gates=gates,
        random_seed=random_seed,
    )
    peak_zone = max(cells, key=lambda c: c["demand_persons"])["h3_id"] if cells else ""

    return {
        "event_id": event_id,
        "horizon_minutes": t_plus_minutes,
        "total_demand": total_demand,
        "peak_zone_h3": peak_zone,
        "cell_count": len(cells),
        "cells": cells,
        "data_source": "SIMULATED",
        "simulated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
