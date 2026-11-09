"""
Pre-configured simulation scenarios.

Provides the canonical RCB vs MI demo scenario used for the
one-click replay demonstration.

All parameters are configurable — the defaults represent the
primary hackathon demo case: RCB vs MI at Chinnaswamy, 34,000 attendance.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Gate definition type ──────────────────────────────────────────────────────

@dataclass
class GateConfig:
    gate_id: str
    name: str
    lat: float
    lon: float
    capacity_pct: float   # fraction of total crowd (0.0–1.0), must sum to 1.0

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "capacity_pct": self.capacity_pct,
        }


# ── Scenario definition ───────────────────────────────────────────────────────

@dataclass
class SimulationScenario:
    """
    A fully parameterised crowd-exit simulation scenario.

    All fields have defaults matching the RCB vs MI demo scenario.
    Override any field to create variant scenarios for testing.
    """

    # Identification
    scenario_id: str = "chinnaswamy_rcb_mi_ipl2027"
    name: str = "RCB vs MI — IPL 2027 (Simulated)"
    description: str = (
        "Simulated IPL cricket match at M. Chinnaswamy Stadium, Bengaluru. "
        "All data is SYNTHETIC — not derived from real-time sources."
    )

    # Venue
    venue_lat: float = 12.9789
    venue_lon: float = 77.5996
    venue_name: str = "M. Chinnaswamy Stadium"

    # Attendance
    attendance: int = 34_000

    # Stadium gates — capacity_pct must sum to 1.0
    gates: list[GateConfig] = field(default_factory=lambda: [
        GateConfig("A", "North Gate",  lat=12.9800, lon=77.5990, capacity_pct=0.25),
        GateConfig("B", "South Gate",  lat=12.9778, lon=77.5996, capacity_pct=0.25),
        GateConfig("C", "East Gate",   lat=12.9789, lon=77.6008, capacity_pct=0.20),
        GateConfig("D", "West Gate",   lat=12.9789, lon=77.5984, capacity_pct=0.20),
        GateConfig("E", "VIP Gate",    lat=12.9795, lon=77.5992, capacity_pct=0.10),
    ])

    # Exit wave parameters
    peak_exit_minute: int = 15      # minute of peak exit rate
    wave_sigma: float = 12.0        # standard deviation of Gaussian wave
    random_seed: int = 42

    # Transport parameters
    metro_surge_active: bool = True
    auto_base_count: int = 120

    # Environment
    weather: str = "clear"          # clear | cloudy | rain (affects auto availability)

    # Simulation horizons
    forecast_horizons: list[int] = field(default_factory=lambda: [20, 40])

    def gates_as_dicts(self) -> list[dict]:
        """Return gates as list of dicts for use in simulator functions."""
        return [g.to_dict() for g in self.gates]

    def validate_gates(self) -> None:
        """Raise ValueError if gate capacity_pct does not sum to approximately 1.0."""
        total = sum(g.capacity_pct for g in self.gates)
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Gate capacity_pct must sum to 1.0, got {total:.4f}. "
                "Adjust gate configurations."
            )

    @property
    def auto_base_count_adjusted(self) -> int:
        """Reduce auto count by 20% in rain (less willing to drive)."""
        if self.weather == "rain":
            return max(0, int(self.auto_base_count * 0.80))
        return self.auto_base_count


# ── Default scenario singleton ────────────────────────────────────────────────

#: The canonical RCB vs MI demo scenario — used by the replay endpoint.
RCB_MI_SCENARIO = SimulationScenario()


# ── Variant scenarios for testing ────────────────────────────────────────────

#: Small crowd scenario — 30,000 attendance
SMALL_CROWD_SCENARIO = SimulationScenario(
    scenario_id="chinnaswamy_small",
    name="Small Crowd Test Scenario",
    attendance=30_000,
    random_seed=100,
)

#: Large crowd scenario — 50,000 attendance (beyond stadium capacity — stress test)
LARGE_CROWD_SCENARIO = SimulationScenario(
    scenario_id="chinnaswamy_large",
    name="Large Crowd Stress Test",
    attendance=50_000,
    random_seed=200,
)

#: Rain scenario — reduced auto availability
RAIN_SCENARIO = SimulationScenario(
    scenario_id="chinnaswamy_rain",
    name="RCB Match — Rain (Simulated)",
    attendance=34_000,
    weather="rain",
    random_seed=42,
)

#: Early-exit scenario — peak at T+8 (result decided early)
EARLY_EXIT_SCENARIO = SimulationScenario(
    scenario_id="chinnaswamy_early_exit",
    name="RCB Match — Early Crowd Exit",
    attendance=34_000,
    peak_exit_minute=8,
    wave_sigma=8.0,
    random_seed=42,
)


# ── Convenience function ──────────────────────────────────────────────────────

def get_scenario(scenario_id: str) -> SimulationScenario:
    """
    Return a scenario by ID. Raises KeyError for unknown IDs.

    Available scenario IDs:
        chinnaswamy_rcb_mi_ipl2027  (default)
        chinnaswamy_small
        chinnaswamy_large
        chinnaswamy_rain
        chinnaswamy_early_exit
    """
    _registry: dict[str, SimulationScenario] = {
        RCB_MI_SCENARIO.scenario_id: RCB_MI_SCENARIO,
        SMALL_CROWD_SCENARIO.scenario_id: SMALL_CROWD_SCENARIO,
        LARGE_CROWD_SCENARIO.scenario_id: LARGE_CROWD_SCENARIO,
        RAIN_SCENARIO.scenario_id: RAIN_SCENARIO,
        EARLY_EXIT_SCENARIO.scenario_id: EARLY_EXIT_SCENARIO,
    }
    if scenario_id not in _registry:
        raise KeyError(
            f"Unknown scenario_id '{scenario_id}'. "
            f"Available: {list(_registry.keys())}"
        )
    return _registry[scenario_id]
