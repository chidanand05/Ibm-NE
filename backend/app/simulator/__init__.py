"""
Simulator package — public API.

Import from here for clean access:
    from app.simulator import simulate_crowd_exit, get_supply_snapshot, simulate_congestion
    from app.simulator import RCB_MI_SCENARIO, get_scenario
    from app.simulator.models import CrowdSimulationResult, SupplySnapshot, TrafficSimulationResult
"""

from app.simulator.crowd import simulate_crowd_exit
from app.simulator.scenarios import (
    RCB_MI_SCENARIO,
    EARLY_EXIT_SCENARIO,
    LARGE_CROWD_SCENARIO,
    RAIN_SCENARIO,
    SMALL_CROWD_SCENARIO,
    SimulationScenario,
    get_scenario,
)
from app.simulator.traffic import simulate_congestion
from app.simulator.transport import get_supply_snapshot

__all__ = [
    # Functions
    "simulate_crowd_exit",
    "get_supply_snapshot",
    "simulate_congestion",
    # Scenario helpers
    "get_scenario",
    "RCB_MI_SCENARIO",
    "SMALL_CROWD_SCENARIO",
    "LARGE_CROWD_SCENARIO",
    "RAIN_SCENARIO",
    "EARLY_EXIT_SCENARIO",
    "SimulationScenario",
]
