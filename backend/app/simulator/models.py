"""
Simulator output schemas.

All Pydantic models used by crowd.py, transport.py, traffic.py, and scenarios.py.
Every model that carries simulation data has data_source: Literal["SIMULATED"] — this
field is NEVER optional and NEVER defaults to anything other than "SIMULATED".

No LLM calls are made anywhere in the simulator package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Common ────────────────────────────────────────────────────────────────────

DemandCategory = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
CongestionLevel = Literal["CLEAR", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
TransportMode = Literal["METRO", "BMTC", "AUTO", "TAXI"]


# ── Crowd simulation ──────────────────────────────────────────────────────────

class ExitWavePoint(BaseModel):
    """One minute of crowd-exit time-series data."""

    minute: int = Field(..., ge=0, le=120, description="Minutes after event end")
    persons_exiting: int = Field(..., ge=0, description="People exiting in this 1-min window")
    cumulative_exited: int = Field(..., ge=0, description="Total people who have exited so far")
    remaining_in_venue: int = Field(..., ge=0, description="People still inside venue")
    data_source: Literal["SIMULATED"] = "SIMULATED"


class GateFlowEstimate(BaseModel):
    """Per-gate egress flow estimate at a given time horizon."""

    gate_id: str
    gate_name: str
    capacity_pct: float = Field(..., ge=0.0, le=1.0, description="Fraction of total crowd through this gate")
    persons_per_minute_peak: int = Field(..., ge=0, description="Peak flow rate (persons/min) at this gate")
    cumulative_exited_20min: int = Field(..., ge=0)
    cumulative_exited_40min: int = Field(..., ge=0)
    lat: float
    lon: float
    data_source: Literal["SIMULATED"] = "SIMULATED"

    @field_validator("cumulative_exited_40min")
    @classmethod
    def t40_gte_t20(cls, v: int, info) -> int:
        t20 = info.data.get("cumulative_exited_20min", 0)
        if v < t20:
            raise ValueError(
                f"cumulative_exited_40min ({v}) must be >= cumulative_exited_20min ({t20})"
            )
        return v


class H3DemandResult(BaseModel):
    """Crowd demand prediction for a single H3 hexagonal cell."""

    h3_id: str = Field(..., description="H3 cell index string (resolution 7)")
    resolution: int = Field(7, ge=1, le=15)
    center_lat: float = Field(..., ge=-90.0, le=90.0)
    center_lon: float = Field(..., ge=-180.0, le=180.0)
    demand_persons: int = Field(..., ge=0)
    demand_category: DemandCategory
    horizon_minutes: int = Field(..., ge=0, description="T+N minutes after event end")
    data_source: Literal["SIMULATED"] = "SIMULATED"


class CrowdSimulationResult(BaseModel):
    """
    Complete crowd-exit simulation result for one time horizon.

    Produced by crowd.py simulate_crowd_exit().
    All values are deterministic given the same input parameters and random_seed.
    """

    event_id: str
    attendance: int = Field(..., gt=0)
    horizon_minutes: int = Field(..., ge=0)
    h3_cells: list[H3DemandResult] = Field(..., min_length=1)
    total_demand: int = Field(..., ge=0, description="Total persons needing transport at this horizon")
    remaining_in_venue: int = Field(..., ge=0, description="Persons still inside stadium at this horizon")
    peak_zone_h3: str = Field(..., description="H3 cell ID with highest demand_persons")
    exit_wave: list[ExitWavePoint] = Field(..., min_length=1)
    gate_flows: list[GateFlowEstimate]
    confidence: float = Field(0.82, ge=0.0, le=1.0, description="Fixed at 0.82 for simulated data")
    data_source: Literal["SIMULATED"] = "SIMULATED"
    simulated_at: datetime

    @field_validator("total_demand")
    @classmethod
    def demand_lte_attendance(cls, v: int, info) -> int:
        att = info.data.get("attendance", 0)
        if v > att:
            raise ValueError(f"total_demand ({v}) cannot exceed attendance ({att})")
        return v

    @field_validator("remaining_in_venue")
    @classmethod
    def remaining_lte_attendance(cls, v: int, info) -> int:
        att = info.data.get("attendance", 0)
        if v > att:
            raise ValueError(f"remaining_in_venue ({v}) cannot exceed attendance ({att})")
        return v


# ── Transport simulation ──────────────────────────────────────────────────────

class SupplyModeResult(BaseModel):
    """Transport supply for one mode at one time horizon."""

    mode: TransportMode
    capacity_per_hour: int = Field(..., ge=0)
    vehicles_available: int = Field(..., ge=0)
    frequency_minutes: int | None = Field(None, ge=1)
    operational: bool = True
    window_capacity: int = Field(..., ge=0, description="Capacity within the time-horizon window")
    gap_persons: int = Field(
        ...,
        description="demand - supply within window; positive = shortage, negative = surplus",
    )
    notes: str = ""
    data_source: Literal["SIMULATED"] = "SIMULATED"

    @field_validator("vehicles_available", "capacity_per_hour", "window_capacity", mode="before")
    @classmethod
    def no_negative(cls, v: int) -> int:
        return max(0, v)


class H3SupplyCell(BaseModel):
    """Supply coverage per H3 cell per mode."""

    h3_id: str
    mode: TransportMode
    capacity_persons: int = Field(..., ge=0)
    data_source: Literal["SIMULATED"] = "SIMULATED"


class SupplySnapshot(BaseModel):
    """
    Complete transport supply snapshot at a given time horizon.

    Produced by transport.py get_supply_snapshot().
    """

    event_id: str
    time_horizon: int = Field(..., ge=0, description="Minutes from event end")
    modes: list[SupplyModeResult] = Field(..., min_length=1)
    total_window_capacity: int = Field(..., ge=0, description="Sum of window_capacity across all modes")
    overall_gap: int = Field(..., description="total_demand - total_window_capacity")
    h3_supply_map: list[H3SupplyCell] = Field(default_factory=list)
    data_source_summary: str = (
        "All transport data is SIMULATED. "
        "Metro schedule based on public timetables with simulated surge. "
        "BMTC and auto counts are synthetic estimates — no real-time GPS data used."
    )
    data_source: Literal["SIMULATED"] = "SIMULATED"
    simulated_at: datetime

    @field_validator("total_window_capacity", mode="before")
    @classmethod
    def no_negative_capacity(cls, v: int) -> int:
        return max(0, v)


# ── Traffic simulation ────────────────────────────────────────────────────────

class CongestionPoint(BaseModel):
    """
    Traffic congestion prediction at a specific road segment / junction.

    Produced by traffic.py simulate_congestion().
    """

    name: str = Field(..., description="Road name or junction description")
    h3_id: str = Field(..., description="H3 cell at resolution 8 covering this segment")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    congestion_level: CongestionLevel
    peak_minute: int = Field(..., ge=0, description="Minute at which congestion peaks")
    congestion_minutes: list[int] = Field(
        default_factory=list,
        description="Minutes (after event end) when this point is congested",
    )
    recommended_diversion: str = ""
    data_source: Literal["SIMULATED"] = "SIMULATED"


class TrafficSimulationResult(BaseModel):
    """
    Complete road congestion simulation around the stadium.

    Produced by traffic.py simulate_congestion().
    """

    event_id: str
    horizon_minutes: int
    congestion_points: list[CongestionPoint]
    critical_roads: list[str] = Field(
        default_factory=list,
        description="Names of roads with CRITICAL or HIGH congestion",
    )
    data_source: Literal["SIMULATED"] = "SIMULATED"
    simulated_at: datetime
