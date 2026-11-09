"""
Unit tests for M5 — Decision Engine.

Pure Python — no mocking required. Tests deterministic scoring.
"""

from __future__ import annotations

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_planner(confidence: float = 0.75, risk_level: str = "HIGH", n_risks: int = 3):
    return {
        "confidence_score": confidence,
        "risk_assessment": {
            "overall_risk": risk_level,
            "top_risks": [f"risk_{i}" for i in range(n_risks)],
            "mitigations": [],
        },
        "strategies_considered": [],
        "recommended_strategy": {"strategy_id": "B"},
        "summary": "Test plan.",
    }


def _make_forecast(
    demand_20: int = 18000,
    attendance: int = 30000,
    demand_40: int = 27000,
):
    return {
        "total_demand_20": demand_20,
        "total_demand_40": demand_40,
        "attendance": attendance,
        "severity": "HIGH",
    }


def _make_supply(gap_20: int = 5000, capacity_20: int = 13000):
    return {
        "overall_gap_20": gap_20,
        "total_capacity_20": capacity_20,
        "adequacy_rating": "STRAINED",
    }


def _make_police(congestion_levels: list[str] | None = None):
    levels = congestion_levels or ["HIGH", "LOW", "MEDIUM", "HIGH", "LOW"]
    return {
        "congestion_points": [{"congestion_level": lv} for lv in levels],
        "critical_roads": [l for l in levels if l == "HIGH"],
    }


# ── score_plan ────────────────────────────────────────────────────────────────

class TestScorePlan:
    def test_returns_tuple_float_str(self):
        from app.services.decision_engine import score_plan
        score, label = score_plan(_make_planner(), _make_forecast())
        assert isinstance(score, float)
        assert isinstance(label, str)
        assert label in ("GREEN", "AMBER", "RED", "CRITICAL")

    def test_score_clamped_0_to_1(self):
        from app.services.decision_engine import score_plan
        # Extreme high-demand case
        score, _ = score_plan(
            _make_planner(confidence=0.0, risk_level="CRITICAL"),
            _make_forecast(demand_20=30000, attendance=30000),
            _make_supply(gap_20=30000, capacity_20=100),
            _make_police(["CRITICAL", "CRITICAL", "CRITICAL"]),
        )
        assert 0.0 <= score <= 1.0

    def test_low_demand_gives_green(self):
        from app.services.decision_engine import score_plan
        score, label = score_plan(
            _make_planner(confidence=0.95, risk_level="LOW", n_risks=0),
            _make_forecast(demand_20=3000, attendance=30000),
            _make_supply(gap_20=0, capacity_20=15000),
            _make_police(["LOW", "LOW", "CLEAR", "LOW", "CLEAR"]),
        )
        assert label in ("GREEN", "AMBER")
        assert score < 0.55

    def test_critical_scenario_gives_red_or_critical(self):
        from app.services.decision_engine import score_plan
        score, label = score_plan(
            _make_planner(confidence=0.4, risk_level="CRITICAL", n_risks=5),
            _make_forecast(demand_20=28000, attendance=30000),
            _make_supply(gap_20=20000, capacity_20=8000),
            _make_police(["CRITICAL", "HIGH", "CRITICAL", "HIGH", "HIGH"]),
        )
        assert label in ("RED", "CRITICAL")
        assert score >= 0.55

    def test_score_increases_with_higher_demand(self):
        from app.services.decision_engine import score_plan
        s1, _ = score_plan(_make_planner(), _make_forecast(demand_20=5000, attendance=30000))
        s2, _ = score_plan(_make_planner(), _make_forecast(demand_20=25000, attendance=30000))
        assert s2 > s1

    def test_score_with_no_supply_output(self):
        """Falls back to internal estimation when supply not passed."""
        from app.services.decision_engine import score_plan
        score, label = score_plan(_make_planner(), _make_forecast())
        assert 0 <= score <= 1
        assert label in ("GREEN", "AMBER", "RED", "CRITICAL")

    def test_score_with_no_police_output(self):
        """Falls back to top_risks count when police not passed."""
        from app.services.decision_engine import score_plan
        score, label = score_plan(_make_planner(n_risks=4), _make_forecast(), _make_supply())
        assert 0 <= score <= 1

    def test_higher_confidence_lowers_score(self):
        from app.services.decision_engine import score_plan
        s_low, _ = score_plan(
            _make_planner(confidence=0.3), _make_forecast(), _make_supply()
        )
        s_high, _ = score_plan(
            _make_planner(confidence=0.95), _make_forecast(), _make_supply()
        )
        assert s_low > s_high


# ── score_components ──────────────────────────────────────────────────────────

class TestScoreComponents:
    def test_returns_all_component_keys(self):
        from app.services.decision_engine import score_components
        result = score_components(_make_planner(), _make_forecast(), _make_supply(), _make_police())
        assert "components" in result
        assert "total_score" in result
        assert "label" in result
        assert "thresholds" in result
        assert "weights" in result

    def test_components_match_expected_keys(self):
        from app.services.decision_engine import score_components
        result = score_components(_make_planner(), _make_forecast(), _make_supply(), _make_police())
        for key in ("demand_pressure", "supply_gap_ratio", "traffic_severity", "planner_confidence"):
            assert key in result["components"]
            comp = result["components"][key]
            assert "raw" in comp
            assert "weight" in comp
            assert "weighted" in comp

    def test_weighted_sum_matches_total(self):
        from app.services.decision_engine import score_components
        result = score_components(_make_planner(), _make_forecast(), _make_supply(), _make_police())
        expected = sum(v["weighted"] for v in result["components"].values())
        assert abs(result["total_score"] - round(min(1.0, max(0.0, expected)), 4)) < 0.0001

    def test_weights_sum_to_one(self):
        from app.services.decision_engine import WEIGHTS
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


# ── _score_to_label ───────────────────────────────────────────────────────────

class TestScoreToLabel:
    def test_label_boundaries(self):
        from app.services.decision_engine import _score_to_label
        assert _score_to_label(0.0) == "GREEN"
        assert _score_to_label(0.34) == "GREEN"
        assert _score_to_label(0.35) == "AMBER"
        assert _score_to_label(0.54) == "AMBER"
        assert _score_to_label(0.55) == "RED"
        assert _score_to_label(0.74) == "RED"
        assert _score_to_label(0.75) == "CRITICAL"
        assert _score_to_label(1.0) == "CRITICAL"

    def test_all_labels_in_expected_set(self):
        from app.services.decision_engine import _score_to_label
        labels = {_score_to_label(s / 100) for s in range(0, 101)}
        assert labels == {"GREEN", "AMBER", "RED", "CRITICAL"}
