"""
Crowd exit simulation engine.

Generates deterministic, synthetic crowd-exit demand data for large events.
All outputs carry data_source="SIMULATED".

Physics model
-------------
Exit wave follows a weighted mixture:
    75% early-leavers  → Normal(μ=peak_minute, σ=wave_sigma)
    25% patient fans   → Uniform(peak_minute, max_minute)

This produces a realistic long-tail distribution observed at cricket matches:
a sharp early peak as result-is-clear fans rush out, followed by gradual drainage.

H3 demand distribution
-----------------------
Crowd is distributed across H3 cells (resolution 7) within walking distance of
the stadium gates using:
  1. Inverse-square attraction toward each gate
  2. Directional pull toward Metro stations (MG Road, Cubbon Park)
  3. Gaussian noise (seed-controlled, reproducible)

NO LLM calls anywhere in this module.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import h3

from app.simulator.models import (
    CrowdSimulationResult,
    DemandCategory,
    ExitWavePoint,
    GateFlowEstimate,
    H3DemandResult,
)

# ── Constants ─────────────────────────────────────────────────────────────────

CONFIDENCE_SIMULATED = 0.82  # Always 0.82 for synthetic data — documented in architecture
SIMULATION_MINUTES = 61       # 0 to 60 inclusive
H3_RESOLUTION = 7
WALKING_RADIUS_KM = 2.5       # H3 cells within this radius of venue center
GRID_DISK_K = 3               # h3.grid_disk(center, k=3) → ~37 cells (approx 2km at res 7)

# Demand thresholds (persons per H3 cell)
DEMAND_THRESHOLDS: dict[str, int] = {
    "CRITICAL": 3000,
    "HIGH": 1500,
    "MEDIUM": 500,
}

# Metro station pull weights: cells closer to Metro get higher demand allocation
# Key: (station_lat, station_lon), value: pull_weight
METRO_ATTRACTION_POINTS = [
    {"lat": 12.9752, "lon": 77.6060, "weight": 0.25, "name": "MG Road Metro"},      # Purple Line
    {"lat": 12.9796, "lon": 77.5930, "weight": 0.18, "name": "Cubbon Park Metro"},   # Green Line
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _demand_category(persons: int) -> DemandCategory:
    if persons >= DEMAND_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if persons >= DEMAND_THRESHOLDS["HIGH"]:
        return "HIGH"
    if persons >= DEMAND_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _lcg_noise(seed: int, index: int, amplitude: float = 0.08) -> float:
    """
    Deterministic pseudo-random noise in [-amplitude, +amplitude].
    Uses a linear congruential generator — no external random library
    dependency; reproducible across Python versions.
    """
    val = (seed * 1664525 + 1013904223 + index * 22695477) & 0xFFFFFFFF
    # Map 0..2^32-1 to -amplitude..+amplitude
    return (val / 0xFFFFFFFF - 0.5) * 2 * amplitude


def _normal_pdf(x: float, mu: float, sigma: float) -> float:
    """Unnormalized normal PDF value at x."""
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


# ── Exit wave ─────────────────────────────────────────────────────────────────

def build_exit_wave(
    attendance: int,
    peak_minute: int = 15,
    wave_sigma: float = 12.0,
    max_minute: int = 60,
    random_seed: int = 42,
) -> list[ExitWavePoint]:
    """
    Build minute-by-minute exit distribution.

    75% early-leavers (Normal centred on peak_minute).
    25% patient fans (Uniform spread from peak_minute to max_minute).

    Guarantees:
    - persons_exiting[t] >= 0 for all t
    - cumulative_exited is strictly non-decreasing
    - cumulative_exited[-1] == attendance (all exits accounted for)
    - remaining_in_venue is non-increasing
    """
    early_fraction = 0.75
    patient_fraction = 1.0 - early_fraction
    early_crowd = int(attendance * early_fraction)
    patient_crowd = attendance - early_crowd

    minutes = list(range(max_minute + 1))

    # ── Early-leavers: Gaussian weights ──────────────────────────────────────
    early_weights = [_normal_pdf(m, peak_minute, wave_sigma) for m in minutes]
    w_sum = sum(early_weights) or 1.0
    early_raw = [early_crowd * w / w_sum for w in early_weights]

    # ── Patient fans: Uniform from peak_minute onward ─────────────────────
    patient_span = max(1, max_minute - peak_minute + 1)
    patient_per_minute = patient_crowd / patient_span
    patient_raw = [
        patient_per_minute if m >= peak_minute else 0.0
        for m in minutes
    ]

    # ── Combine and apply reproducible noise ──────────────────────────────
    combined = [e + p for e, p in zip(early_raw, patient_raw)]
    noisy = [
        max(0.0, v * (1 + _lcg_noise(random_seed, i, amplitude=0.05)))
        for i, v in enumerate(combined)
    ]

    # ── Scale to exactly match attendance ─────────────────────────────────
    total = sum(noisy) or 1.0
    scaled = [v / total * attendance for v in noisy]

    # ── Round to integers, fix rounding error on last bucket ──────────────
    rounded = [max(0, round(v)) for v in scaled]
    diff = attendance - sum(rounded)
    # Apply rounding correction to the peak minute (largest bucket)
    peak_idx = max(range(len(rounded)), key=lambda i: rounded[i])
    rounded[peak_idx] = max(0, rounded[peak_idx] + diff)

    # ── Build output with cumulative and remaining ────────────────────────
    wave: list[ExitWavePoint] = []
    cumulative = 0
    for minute, exiting in enumerate(rounded):
        cumulative += exiting
        remaining = max(0, attendance - cumulative)
        wave.append(
            ExitWavePoint(
                minute=minute,
                persons_exiting=exiting,
                cumulative_exited=cumulative,
                remaining_in_venue=remaining,
                data_source="SIMULATED",
            )
        )
    return wave


# ── Gate distribution ─────────────────────────────────────────────────────────

def build_gate_flows(
    attendance: int,
    gates: list[dict[str, Any]],
    wave: list[ExitWavePoint],
    random_seed: int = 42,
) -> list[GateFlowEstimate]:
    """
    Distribute crowd across gates proportional to gate capacity_pct with small noise.

    Normalizes so gate fractions always sum to 1.0.
    T+40 >= T+20 is enforced by the validator in GateFlowEstimate.
    """
    n = len(gates)
    if n == 0:
        return []

    # Build noisy fractions from capacity_pct
    raw_fractions = []
    for i, gate in enumerate(gates):
        base = float(gate.get("capacity_pct", 1.0 / n))
        noise = _lcg_noise(random_seed + 1000, i, amplitude=0.03)
        raw_fractions.append(max(0.0, base + noise))

    # Normalize so they sum to exactly 1.0
    total = sum(raw_fractions) or 1.0
    fractions = [f / total for f in raw_fractions]

    # Cumulative exits at T+20 and T+40
    cum_20 = next((p.cumulative_exited for p in wave if p.minute == 20), wave[-1].cumulative_exited)
    cum_40 = next((p.cumulative_exited for p in wave if p.minute == 40), wave[-1].cumulative_exited)

    # Peak persons/minute for each gate (occurs at wave peak minute)
    peak_point = max(wave, key=lambda p: p.persons_exiting)

    results: list[GateFlowEstimate] = []
    for i, (gate, frac) in enumerate(zip(gates, fractions)):
        g20 = max(0, round(cum_20 * frac))
        g40 = max(g20, round(cum_40 * frac))  # enforce monotonic
        peak_flow = max(1, round(peak_point.persons_exiting * frac))

        results.append(
            GateFlowEstimate(
                gate_id=gate["gate_id"],
                gate_name=gate.get("name", gate["gate_id"]),
                capacity_pct=frac,
                persons_per_minute_peak=peak_flow,
                cumulative_exited_20min=g20,
                cumulative_exited_40min=g40,
                lat=float(gate["lat"]),
                lon=float(gate["lon"]),
                data_source="SIMULATED",
            )
        )
    return results


# ── H3 demand distribution ────────────────────────────────────────────────────

def build_h3_demand(
    total_demand: int,
    venue_lat: float,
    venue_lon: float,
    horizon_minutes: int,
    gates: list[dict[str, Any]],
    random_seed: int = 42,
    resolution: int = H3_RESOLUTION,
    grid_k: int = GRID_DISK_K,
) -> list[H3DemandResult]:
    """
    Distribute total_demand across H3 cells around the venue.

    Weight formula per cell:
        w(cell) = Σ_gates [gate_frac / max(0.1, dist_km(cell, gate)²)]
                + Σ_metro  [metro_weight / max(0.1, dist_km(cell, metro)²)]
                + noise

    Demand is proportional to weight.
    Cells with 0 demand after rounding are retained (demand=0, category=LOW).
    """
    # Venue center H3 cell and its k-ring
    center_h3 = h3.latlng_to_cell(venue_lat, venue_lon, resolution)
    cell_ids: list[str] = list(h3.grid_disk(center_h3, grid_k))

    if not cell_ids:
        cell_ids = [center_h3]

    # Gate fractions (re-derive deterministically from gate capacity_pct)
    n_gates = len(gates)
    gate_fracs: list[float] = []
    raw_fracs = []
    for i, gate in enumerate(gates):
        base = float(gate.get("capacity_pct", 1.0 / max(n_gates, 1)))
        noise = _lcg_noise(random_seed + 1000, i, amplitude=0.03)
        raw_fracs.append(max(0.0, base + noise))
    total_f = sum(raw_fracs) or 1.0
    gate_fracs = [f / total_f for f in raw_fracs]

    # Compute weight for each cell
    weights: list[float] = []
    for idx, cell_id in enumerate(cell_ids):
        clat, clon = h3.cell_to_latlng(cell_id)

        # Gate attraction (inverse square distance, floored at 0.1 km)
        gate_w = 0.0
        for gate, frac in zip(gates, gate_fracs):
            d = max(0.1, _haversine_km(clat, clon, float(gate["lat"]), float(gate["lon"])))
            gate_w += frac / (d * d)

        # Metro attraction (fixed weights from METRO_ATTRACTION_POINTS)
        metro_w = 0.0
        for mp in METRO_ATTRACTION_POINTS:
            d = max(0.1, _haversine_km(clat, clon, mp["lat"], mp["lon"]))
            metro_w += mp["weight"] / (d * d)

        # Small reproducible noise
        noise = 1.0 + _lcg_noise(random_seed + 2000, idx, amplitude=0.08)

        weights.append(max(0.0, (gate_w + metro_w * 0.4) * noise))

    w_total = sum(weights) or 1.0
    raw_demand = [total_demand * w / w_total for w in weights]

    # Round to integers, fix residual
    demands = [max(0, round(v)) for v in raw_demand]
    residual = total_demand - sum(demands)
    if residual != 0:
        # Apply to the highest-weight cell
        peak_idx = max(range(len(weights)), key=lambda i: weights[i])
        demands[peak_idx] = max(0, demands[peak_idx] + residual)

    results: list[H3DemandResult] = []
    for cell_id, demand in zip(cell_ids, demands):
        clat, clon = h3.cell_to_latlng(cell_id)
        results.append(
            H3DemandResult(
                h3_id=cell_id,
                resolution=resolution,
                center_lat=round(clat, 6),
                center_lon=round(clon, 6),
                demand_persons=demand,
                demand_category=_demand_category(demand),
                horizon_minutes=horizon_minutes,
                data_source="SIMULATED",
            )
        )
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def simulate_crowd_exit(
    event_id: str,
    t_plus_minutes: int,
    attendance: int,
    venue_lat: float,
    venue_lon: float,
    gates: list[dict[str, Any]],
    peak_minute: int = 15,
    wave_sigma: float = 12.0,
    random_seed: int = 42,
) -> CrowdSimulationResult:
    """
    Simulate crowd-exit demand at T+N minutes after event end.

    Parameters
    ----------
    event_id        Unique event identifier (stored in result, no DB lookup).
    t_plus_minutes  Minutes after event end to forecast for (typically 20 or 40).
    attendance      Total expected attendance.
    venue_lat/lon   Venue centre coordinates.
    gates           List of gate dicts: {gate_id, name, lat, lon, capacity_pct}.
    peak_minute     Minute of peak exit rate (default 15).
    wave_sigma      Standard deviation of exit Gaussian (default 12.0).
    random_seed     Seed for deterministic noise (default 42).

    Returns
    -------
    CrowdSimulationResult — fully validated Pydantic model.
    """
    wave = build_exit_wave(
        attendance=attendance,
        peak_minute=peak_minute,
        wave_sigma=wave_sigma,
        random_seed=random_seed,
    )

    # Cumulative exits by t_plus_minutes
    cum_at_horizon = next(
        (p.cumulative_exited for p in wave if p.minute == t_plus_minutes),
        wave[-1].cumulative_exited,
    )
    remaining_at_horizon = next(
        (p.remaining_in_venue for p in wave if p.minute == t_plus_minutes),
        0,
    )

    # People who have exited but still need transport (demand) = those outside venue
    total_demand = min(cum_at_horizon, attendance)

    gate_flows = build_gate_flows(
        attendance=attendance,
        gates=gates,
        wave=wave,
        random_seed=random_seed,
    )

    h3_cells = build_h3_demand(
        total_demand=total_demand,
        venue_lat=venue_lat,
        venue_lon=venue_lon,
        horizon_minutes=t_plus_minutes,
        gates=gates,
        random_seed=random_seed,
    )

    peak_zone = max(h3_cells, key=lambda c: c.demand_persons).h3_id if h3_cells else ""

    return CrowdSimulationResult(
        event_id=event_id,
        attendance=attendance,
        horizon_minutes=t_plus_minutes,
        h3_cells=h3_cells,
        total_demand=total_demand,
        remaining_in_venue=remaining_at_horizon,
        peak_zone_h3=peak_zone,
        exit_wave=wave,
        gate_flows=gate_flows,
        confidence=CONFIDENCE_SIMULATED,
        data_source="SIMULATED",
        simulated_at=datetime.now(tz=timezone.utc),
    )
