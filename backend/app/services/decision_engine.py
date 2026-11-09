"""
Decision Engine — deterministic scoring for action plans.

Produces a normalized 0–1 risk score and traffic-light label
(GREEN / AMBER / RED / CRITICAL) from agent outputs, without any LLM call.

Used by the Planner node to annotate plans before presenting to the
human approver.

Score formula (all components 0–1, weighted sum):
  - demand_pressure    : total_demand_20 / attendance           (weight 0.35)
  - supply_gap_ratio   : overall_gap_20 / total_demand_20       (weight 0.30)
  - traffic_severity   : fraction of roads at HIGH/CRITICAL     (weight 0.20)
  - planner_confidence : 1 - confidence_score                   (weight 0.15)

Final score clamped to [0, 1]. Higher = more critical / needs more attention.
"""

from __future__ import annotations

from typing import Any

# ── Weights ───────────────────────────────────────────────────────────────────

WEIGHTS = {
    "demand_pressure": 0.35,
    "supply_gap_ratio": 0.30,
    "traffic_severity": 0.20,
    "planner_confidence": 0.15,
}

# ── Label thresholds ──────────────────────────────────────────────────────────

THRESHOLDS = {
    "CRITICAL": 0.75,
    "RED":      0.55,
    "AMBER":    0.35,
    "GREEN":    0.0,
}

# ── Scoring severity maps ─────────────────────────────────────────────────────

ADEQUACY_TO_SEVERITY = {
    "ADEQUATE": 0.0,
    "STRAINED": 0.4,
    "INADEQUATE": 0.7,
    "CRITICAL": 1.0,
}

RISK_TO_SCORE = {
    "LOW": 0.1,
    "MEDIUM": 0.4,
    "HIGH": 0.7,
    "CRITICAL": 1.0,
}


# ── Public API ────────────────────────────────────────────────────────────────

def score_plan(
    planner_output: dict[str, Any],
    egress_forecast: dict[str, Any],
    supply_output: dict[str, Any] | None = None,
    police_output: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """
    Compute a normalized 0–1 risk score and traffic-light label.

    Parameters
    ----------
    planner_output   Output dict from PlannerAgent.run()
    egress_forecast  Output dict from EgressForecastAgent.run()
    supply_output    Optional SupplyAgent output (if available)
    police_output    Optional PoliceCoordinationAgent output (if available)

    Returns
    -------
    (score: float, label: str)  where label ∈ {GREEN, AMBER, RED, CRITICAL}
    """
    # ── Component 1: demand pressure ──────────────────────────────────────
    total_demand_20 = int(egress_forecast.get("total_demand_20", 0))
    attendance = int(egress_forecast.get("attendance", max(total_demand_20, 1)))
    demand_pressure = min(1.0, total_demand_20 / max(attendance, 1))

    # ── Component 2: supply gap ratio ─────────────────────────────────────
    if supply_output is not None:
        overall_gap = int(supply_output.get("overall_gap_20", 0))
        total_cap = int(supply_output.get("total_capacity_20", 1))
    else:
        # Infer from planner if supply not passed directly
        risk_level = planner_output.get("risk_assessment", {}).get("overall_risk", "MEDIUM")
        overall_gap = int(total_demand_20 * RISK_TO_SCORE.get(risk_level, 0.4))
        total_cap = max(total_demand_20 - overall_gap, 1)

    supply_gap_ratio = min(1.0, max(0.0, overall_gap / max(total_demand_20, 1)))

    # ── Component 3: traffic severity ─────────────────────────────────────
    if police_output is not None:
        congestion_points = police_output.get("congestion_points", [])
        if congestion_points:
            high_or_critical = sum(
                1 for p in congestion_points
                if p.get("congestion_level") in ("HIGH", "CRITICAL")
            )
            traffic_severity = high_or_critical / len(congestion_points)
        else:
            traffic_severity = 0.3  # default when no data
    else:
        # Estimate from critical_roads count if police output not available
        critical_count = len(planner_output.get("risk_assessment", {}).get("top_risks", []))
        traffic_severity = min(1.0, critical_count * 0.2)

    # ── Component 4: planner confidence (inverted) ────────────────────────
    confidence = float(planner_output.get("confidence_score", 0.75))
    planner_confidence = max(0.0, 1.0 - confidence)

    # ── Weighted sum ──────────────────────────────────────────────────────
    score = (
        demand_pressure    * WEIGHTS["demand_pressure"]
        + supply_gap_ratio   * WEIGHTS["supply_gap_ratio"]
        + traffic_severity   * WEIGHTS["traffic_severity"]
        + planner_confidence * WEIGHTS["planner_confidence"]
    )
    score = round(min(1.0, max(0.0, score)), 4)

    # ── Label ─────────────────────────────────────────────────────────────
    label = _score_to_label(score)

    return score, label


def _score_to_label(score: float) -> str:
    """Map 0–1 score to traffic-light label."""
    if score >= THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= THRESHOLDS["RED"]:
        return "RED"
    if score >= THRESHOLDS["AMBER"]:
        return "AMBER"
    return "GREEN"


def score_components(
    planner_output: dict[str, Any],
    egress_forecast: dict[str, Any],
    supply_output: dict[str, Any] | None = None,
    police_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return detailed component breakdown for debugging / display.

    Returns dict with individual component scores, weights, weighted values,
    total score, and label.
    """
    total_demand_20 = int(egress_forecast.get("total_demand_20", 0))
    attendance = int(egress_forecast.get("attendance", max(total_demand_20, 1)))
    demand_pressure = min(1.0, total_demand_20 / max(attendance, 1))

    if supply_output is not None:
        overall_gap = int(supply_output.get("overall_gap_20", 0))
    else:
        risk_level = planner_output.get("risk_assessment", {}).get("overall_risk", "MEDIUM")
        overall_gap = int(total_demand_20 * RISK_TO_SCORE.get(risk_level, 0.4))

    supply_gap_ratio = min(1.0, max(0.0, overall_gap / max(total_demand_20, 1)))

    if police_output is not None:
        congestion_points = police_output.get("congestion_points", [])
        if congestion_points:
            high_or_critical = sum(
                1 for p in congestion_points
                if p.get("congestion_level") in ("HIGH", "CRITICAL")
            )
            traffic_severity = high_or_critical / len(congestion_points)
        else:
            traffic_severity = 0.3
    else:
        critical_count = len(planner_output.get("risk_assessment", {}).get("top_risks", []))
        traffic_severity = min(1.0, critical_count * 0.2)

    confidence = float(planner_output.get("confidence_score", 0.75))
    planner_confidence = max(0.0, 1.0 - confidence)

    components = {
        "demand_pressure": {"raw": demand_pressure, "weight": WEIGHTS["demand_pressure"]},
        "supply_gap_ratio": {"raw": supply_gap_ratio, "weight": WEIGHTS["supply_gap_ratio"]},
        "traffic_severity": {"raw": traffic_severity, "weight": WEIGHTS["traffic_severity"]},
        "planner_confidence": {"raw": planner_confidence, "weight": WEIGHTS["planner_confidence"]},
    }
    for k, v in components.items():
        v["weighted"] = round(v["raw"] * v["weight"], 4)

    total = sum(v["weighted"] for v in components.values())
    total = round(min(1.0, max(0.0, total)), 4)

    return {
        "components": components,
        "total_score": total,
        "label": _score_to_label(total),
        "thresholds": THRESHOLDS,
        "weights": WEIGHTS,
    }
