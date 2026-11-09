"""
Unit tests for M3 — All 7 Namma Exodus agents.

All LLM calls, DB operations, and external services are mocked.
No Docker, no PostgreSQL, no ChromaDB required.

Tests per agent:
  - Successful run with mocked LLM returning valid JSON
  - LLM fallback path (LLMGatewayError → deterministic defaults)
  - _fallback_output() structure validation
  - Key output fields presence and types
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Shared test fixtures ──────────────────────────────────────────────────────

EVENT_ID = "20000000-0000-0000-0000-000000000001"
SESSION_ID = str(uuid.uuid4())


def _make_db_session():
    """Return a minimal AsyncSession mock."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _make_exec_row(exec_id: str | None = None):
    row = MagicMock()
    row.id = exec_id or str(uuid.uuid4())
    row.status = "RUNNING"
    return row


BASE_INPUT = {
    "event_id": EVENT_ID,
    "event_name": "RCB vs CSK IPL 2026",
    "attendance": 30000,
    "venue_lat": 12.9789,
    "venue_lon": 77.5996,
    "gates": [
        {"gate_id": "A", "name": "North Gate", "lat": 12.9800, "lon": 77.5990, "capacity_pct": 0.25},
        {"gate_id": "B", "name": "South Gate", "lat": 12.9778, "lon": 77.5996, "capacity_pct": 0.25},
        {"gate_id": "C", "name": "East Gate",  "lat": 12.9789, "lon": 77.6008, "capacity_pct": 0.20},
        {"gate_id": "D", "name": "West Gate",  "lat": 12.9789, "lon": 77.5984, "capacity_pct": 0.20},
        {"gate_id": "E", "name": "VIP Gate",   "lat": 12.9795, "lon": 77.5992, "capacity_pct": 0.10},
    ],
}


# ── BaseAgent ─────────────────────────────────────────────────────────────────

class TestBaseAgent:
    def test_instantiation(self):
        from app.agents.base import BaseAgent
        agent = BaseAgent()
        assert agent.agent_id == "base"
        assert agent.task_type == "structured_extraction"

    def test_fallback_output_structure(self):
        from app.agents.base import BaseAgent
        agent = BaseAgent()
        out = agent._fallback_output({}, reason="test_error")
        assert out["llm_fallback"] is True
        assert out["fallback_reason"] == "test_error"
        assert out["agent_id"] == "base"
        assert out["data_source"] == "SIMULATED"

    @pytest.mark.asyncio
    async def test_execute_calls_run_and_saves_db(self):
        from app.agents.base import BaseAgent

        class DummyAgent(BaseAgent):
            agent_id = "dummy"
            async def run(self, input_data, db, *, exec_id, event_id):
                return {"result": "ok", "data_source": "SIMULATED", "llm_fallback": False}

        db = _make_db_session()
        row = _make_exec_row()
        with patch.object(DummyAgent, "_create_execution", new=AsyncMock(return_value=row)):
            with patch.object(DummyAgent, "_finish_execution", new=AsyncMock()):
                agent = DummyAgent()
                out = await agent.execute(BASE_INPUT, db, SESSION_ID, EVENT_ID)
        assert out["result"] == "ok"
        assert out["exec_id"] == row.id

    @pytest.mark.asyncio
    async def test_execute_catches_run_exception(self):
        from app.agents.base import BaseAgent

        class FailingAgent(BaseAgent):
            agent_id = "failing"
            async def run(self, input_data, db, *, exec_id, event_id):
                raise RuntimeError("boom")

        db = _make_db_session()
        row = _make_exec_row()
        with patch.object(FailingAgent, "_create_execution", new=AsyncMock(return_value=row)):
            with patch.object(FailingAgent, "_finish_execution", new=AsyncMock()):
                agent = FailingAgent()
                out = await agent.execute(BASE_INPUT, db, SESSION_ID, EVENT_ID)
        assert out["llm_fallback"] is True
        assert "boom" in out["fallback_reason"]


# ── EventIntelligenceAgent ────────────────────────────────────────────────────

class TestEventIntelligenceAgent:
    def _make_agent(self):
        from app.agents.event_intelligence import EventIntelligenceAgent
        agent = EventIntelligenceAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_llm_success(self):
        agent = self._make_agent()
        llm_json = {
            "risk_level": "HIGH",
            "crowd_category": "LARGE",
            "key_risks": ["MG Road congestion"],
            "recommendations": ["Activate Metro surge"],
            "summary": "High risk event.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))

        db = _make_db_session()
        with patch("app.mcp_servers.history_server.retrieve_similar_events", return_value=[]):
            out = await agent.run(BASE_INPUT, db, exec_id="x1", event_id=EVENT_ID)

        assert out["risk_level"] == "HIGH"
        assert out["crowd_category"] == "LARGE"
        assert out["llm_fallback"] is False
        assert out["data_source"] == "SIMULATED"
        assert out["attendance"] == 30000
        assert len(out["gates"]) == 5

    @pytest.mark.asyncio
    async def test_run_llm_fallback(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("structured_extraction", ["m1"], RuntimeError("fail"))
        )

        db = _make_db_session()
        with patch("app.mcp_servers.history_server.retrieve_similar_events", return_value=[]):
            out = await agent.run(BASE_INPUT, db, exec_id="x1", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert out["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_default_analysis_mega_event(self):
        from app.agents.event_intelligence import EventIntelligenceAgent
        agent = EventIntelligenceAgent()
        result = agent._default_analysis(40000)
        assert result["risk_level"] == "CRITICAL"
        assert result["crowd_category"] == "MEGA"

    def test_default_analysis_large_event(self):
        from app.agents.event_intelligence import EventIntelligenceAgent
        agent = EventIntelligenceAgent()
        result = agent._default_analysis(28000)
        assert result["risk_level"] == "HIGH"
        assert result["crowd_category"] == "LARGE"

    def test_fallback_output_has_required_keys(self):
        from app.agents.event_intelligence import EventIntelligenceAgent
        agent = EventIntelligenceAgent()
        out = agent._fallback_output(BASE_INPUT)
        for key in ("risk_level", "crowd_category", "gates", "venue_lat", "venue_lon"):
            assert key in out, f"Missing key: {key}"


# ── EgressForecastAgent ───────────────────────────────────────────────────────

class TestEgressForecastAgent:
    def _make_agent(self):
        from app.agents.egress_forecast import EgressForecastAgent
        agent = EgressForecastAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_sim_runs_without_llm_error(self):
        """Simulation must produce valid output even with LLM failure."""
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("structured_extraction", ["m"], RuntimeError("no key"))
        )
        db = _make_db_session()
        out = await agent.run(BASE_INPUT, db, exec_id="x2", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert out["total_demand_20"] > 0
        assert out["total_demand_40"] >= out["total_demand_20"]
        assert out["data_source"] == "SIMULATED"
        assert len(out["gate_flows"]) == 5

    @pytest.mark.asyncio
    async def test_run_llm_success_sets_severity(self):
        agent = self._make_agent()
        llm_json = {
            "severity": "CRITICAL",
            "peak_period": "T+10 to T+25",
            "bottlenecks": ["MG Road"],
            "stagger_recommendation": "Release gates staggered",
            "summary": "Critical egress.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        db = _make_db_session()
        out = await agent.run(BASE_INPUT, db, exec_id="x2", event_id=EVENT_ID)
        assert out["severity"] == "CRITICAL"
        assert out["llm_fallback"] is False

    def test_fallback_output_structure(self):
        from app.agents.egress_forecast import EgressForecastAgent
        agent = EgressForecastAgent()
        out = agent._fallback_output(BASE_INPUT)
        assert "total_demand_20" in out
        assert out["confidence"] == 0.82


# ── SupplyAgent ───────────────────────────────────────────────────────────────

class TestSupplyAgent:
    def _make_agent(self):
        from app.agents.supply import SupplyAgent
        agent = SupplyAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_computes_gap(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("structured_extraction", ["m"], RuntimeError("no"))
        )
        input_data = {**BASE_INPUT, "total_demand_20": 18000, "total_demand_40": 27000}
        db = _make_db_session()
        out = await agent.run(input_data, db, exec_id="x3", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert "overall_gap_20" in out
        assert "gap_by_mode" in out
        assert out["data_source"] == "SIMULATED"

    @pytest.mark.asyncio
    async def test_run_llm_success(self):
        agent = self._make_agent()
        llm_json = {
            "adequacy_rating": "INADEQUATE",
            "metro_actions": ["Activate surge"],
            "bmtc_actions": ["Deploy buses"],
            "auto_actions": ["Direct autos"],
            "priority_mode": "METRO",
            "additional_vehicles_needed": 8,
            "summary": "Supply inadequate.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        input_data = {**BASE_INPUT, "total_demand_20": 18000, "total_demand_40": 27000}
        db = _make_db_session()
        out = await agent.run(input_data, db, exec_id="x3", event_id=EVENT_ID)

        assert out["adequacy_rating"] == "INADEQUATE"
        assert out["surge_recommended"] is True
        assert out["llm_fallback"] is False

    def test_fallback_output_has_gap_fields(self):
        from app.agents.supply import SupplyAgent
        agent = SupplyAgent()
        out = agent._fallback_output(BASE_INPUT)
        assert "overall_gap_20" in out
        assert "priority_mode" in out


# ── PoliceCoordinationAgent ───────────────────────────────────────────────────

class TestPoliceCoordinationAgent:
    def _make_agent(self):
        from app.agents.police_coordination import PoliceCoordinationAgent
        agent = PoliceCoordinationAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_congestion_simulation_fires(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("structured_extraction", ["m"], RuntimeError("no"))
        )
        db = _make_db_session()
        out = await agent.run(BASE_INPUT, db, exec_id="x4", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert len(out["congestion_points"]) == 5  # 5 road segments
        assert len(out["critical_roads"]) >= 1
        assert out["data_source"] == "SIMULATED"

    @pytest.mark.asyncio
    async def test_run_llm_success(self):
        agent = self._make_agent()
        llm_json = {
            "deployment_zones": [{"location": "MG Road", "personnel_count": 6, "role": "Traffic"}],
            "diversion_routes": ["Use Residency Road"],
            "gate_sequence": ["A", "B", "C", "D", "E"],
            "estimated_clearance_minutes": 40,
            "summary": "Deploy 6 at MG Road.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        db = _make_db_session()
        out = await agent.run(BASE_INPUT, db, exec_id="x4", event_id=EVENT_ID)

        assert out["estimated_clearance_minutes"] == 40
        assert out["llm_fallback"] is False

    def test_default_deployments_has_personnel(self):
        from app.agents.police_coordination import PoliceCoordinationAgent
        agent = PoliceCoordinationAgent()
        result = agent._default_deployments(["MG Road"])
        assert len(result["deployment_zones"]) >= 2
        assert result["estimated_clearance_minutes"] > 0


# ── PlannerAgent ──────────────────────────────────────────────────────────────

class TestPlannerAgent:
    def _make_input(self):
        return {
            "event_id": EVENT_ID,
            "event_intelligence": {
                "event_name": "RCB vs CSK", "attendance": 30000,
                "risk_level": "HIGH", "historical_context": "RCB vs CSK 2026: Metro gap.",
            },
            "egress_forecast": {
                "total_demand_20": 18000, "total_demand_40": 27000, "severity": "HIGH",
            },
            "supply": {
                "adequacy_rating": "STRAINED", "overall_gap_20": 5000,
                "metro_actions": ["Activate surge"], "bmtc_actions": ["Deploy buses"],
                "auto_actions": ["Direct autos"], "priority_mode": "METRO",
                "deployment_actions": [],
            },
            "police_coordination": {
                "critical_roads": ["MG Road"],
                "deployment_zones": [], "estimated_clearance_minutes": 45,
            },
        }

    def _make_agent(self):
        from app.agents.planner import PlannerAgent
        agent = PlannerAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_llm_fallback_returns_valid_plan(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("strategic_planning", ["m"], RuntimeError("no"))
        )
        db = _make_db_session()
        out = await agent.run(self._make_input(), db, exec_id="x5", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert out["requires_human_approval"] is True
        assert isinstance(out["confidence_score"], float)
        assert 0 <= out["confidence_score"] <= 1
        assert len(out["gate_release_sequence"]) == 5

    @pytest.mark.asyncio
    async def test_run_llm_success_sets_recommended_strategy(self):
        agent = self._make_agent()
        llm_json = {
            "strategies_considered": [{"strategy_id": "B", "name": "Balanced", "pros": [], "cons": []}],
            "recommended_strategy": {"strategy_id": "B", "name": "Balanced", "rationale": "Best fit."},
            "metro_actions": ["Surge active"],
            "bmtc_actions": ["Buses deployed"],
            "auto_actions": ["Autos directed"],
            "police_actions": ["6 at MG Road"],
            "gate_release_sequence": [
                {"gate_id": "A", "delay_minutes": 0},
                {"gate_id": "B", "delay_minutes": 0},
            ],
            "risk_assessment": {"overall_risk": "HIGH", "top_risks": [], "mitigations": []},
            "confidence_score": 0.82,
            "summary": "Balanced plan approved.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        db = _make_db_session()
        out = await agent.run(self._make_input(), db, exec_id="x5", event_id=EVENT_ID)

        assert out["recommended_strategy"]["strategy_id"] == "B"
        assert out["confidence_score"] == 0.82
        assert out["requires_human_approval"] is True
        assert out["llm_fallback"] is False


# ── CitizenGuidanceAgent ──────────────────────────────────────────────────────

class TestCitizenGuidanceAgent:
    def _make_input(self):
        return {
            "event_id": EVENT_ID,
            "event_intelligence": {"event_name": "RCB vs CSK"},
            "planner": {
                "gate_release_sequence": [
                    {"gate_id": "A", "delay_minutes": 0},
                    {"gate_id": "B", "delay_minutes": 0},
                    {"gate_id": "C", "delay_minutes": 5},
                    {"gate_id": "D", "delay_minutes": 5},
                    {"gate_id": "E", "delay_minutes": 10},
                ],
                "metro_actions": ["Activate Purple Line surge"],
                "bmtc_actions": ["Deploy 6 buses at KG Road"],
            },
            "supply": {"priority_mode": "METRO"},
        }

    def _make_agent(self):
        from app.agents.citizen_guidance import CitizenGuidanceAgent
        agent = CitizenGuidanceAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_llm_fallback_returns_all_languages(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("multilingual_translation", ["m"], RuntimeError("no"))
        )
        db = _make_db_session()
        out = await agent.run(self._make_input(), db, exec_id="x6", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert out["languages"] == ["english", "kannada", "hindi"]
        assert "english" in out["general_guidance"]
        assert "kannada" in out["general_guidance"]
        assert "hindi" in out["general_guidance"]

    @pytest.mark.asyncio
    async def test_run_llm_success_all_gates(self):
        agent = self._make_agent()
        llm_json = {
            "by_gate": {
                "A": {"english": "Gate A: walk to Metro.", "kannada": "ಎ: ಮೆಟ್ರೋ.", "hindi": "ए: मेट्रो।"},
                "B": {"english": "Gate B: BMTC.", "kannada": "ಬಿ: ಬಸ್.", "hindi": "बी: बस।"},
            },
            "general": {
                "english": "Walk calmly.", "kannada": "ಶಾಂತವಾಗಿ ನಡೆಯಿರಿ.", "hindi": "शांत रहें।",
            },
            "metro": {
                "english": "MG Road Metro 12 min.", "kannada": "ಮೆಟ್ರೋ 12 ನಿ.", "hindi": "मेट्रो 12 मि.",
            },
            "safety_message": {
                "english": "Do not rush.", "kannada": "ಆತುರ ಪಡಬೇಡಿ.", "hindi": "जल्दी मत करें।",
            },
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        db = _make_db_session()
        out = await agent.run(self._make_input(), db, exec_id="x6", event_id=EVENT_ID)

        assert out["llm_fallback"] is False
        assert "A" in out["guidance_by_gate"]
        assert out["metro_instructions"]["english"] == "MG Road Metro 12 min."

    def test_default_guidance_covers_all_gates(self):
        from app.agents.citizen_guidance import CitizenGuidanceAgent
        agent = CitizenGuidanceAgent()
        gate_seq = [{"gate_id": g, "delay_minutes": i * 5} for i, g in enumerate(["A","B","C","D","E"])]
        guidance = agent._default_guidance(gate_seq)
        for gate in ["A", "B", "C", "D", "E"]:
            assert gate in guidance["by_gate"]
            assert "english" in guidance["by_gate"][gate]
            assert "kannada" in guidance["by_gate"][gate]


# ── LearningAgent ─────────────────────────────────────────────────────────────

class TestLearningAgent:
    def _make_input(self):
        return {
            "event_id": EVENT_ID,
            "event_intelligence": {
                "event_name": "RCB vs CSK", "attendance": 30000, "risk_level": "HIGH",
            },
            "egress_forecast": {
                "total_demand_20": 18000, "total_demand_40": 27000, "confidence": 0.82,
            },
            "supply": {"adequacy_rating": "STRAINED", "overall_gap_20": 5000},
            "police_coordination": {"estimated_clearance_minutes": 45},
            "planner": {"confidence_score": 0.78, "summary": "Balanced plan."},
        }

    def _make_agent(self):
        from app.agents.learning import LearningAgent
        agent = LearningAgent()
        agent._llm = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_run_computes_accuracy_metrics(self):
        from app.llm_gateway.client import LLMGatewayError
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(
            side_effect=LLMGatewayError("structured_extraction", ["m"], RuntimeError("no"))
        )
        with patch("app.mcp_servers.history_server.store_event_outcome", return_value=EVENT_ID):
            db = _make_db_session()
            out = await agent.run(self._make_input(), db, exec_id="x7", event_id=EVENT_ID)

        assert out["llm_fallback"] is True
        assert "accuracy_metrics" in out
        assert out["accuracy_metrics"]["predicted_demand_20"] == 18000
        assert "demand_error_pct" in out["accuracy_metrics"]

    @pytest.mark.asyncio
    async def test_run_llm_success_extracts_lessons(self):
        agent = self._make_agent()
        llm_json = {
            "lessons_learned": ["Metro surge proved sufficient", "Auto depleted fast"],
            "model_improvements": ["Increase patience fraction"],
            "accuracy_grade": "A",
            "drift_detected": False,
            "summary": "Good accuracy.",
        }
        agent._llm.complete = AsyncMock(return_value=MagicMock(content=json.dumps(llm_json)))
        with patch("app.mcp_servers.history_server.store_event_outcome", return_value=EVENT_ID):
            db = _make_db_session()
            out = await agent.run(self._make_input(), db, exec_id="x7", event_id=EVENT_ID)

        assert out["accuracy_grade"] == "A"
        assert "Metro surge proved sufficient" in out["lessons_learned"]
        assert out["stored_in_chroma"] is True
        assert out["llm_fallback"] is False

    @pytest.mark.asyncio
    async def test_run_chroma_failure_handled_gracefully(self):
        """ChromaDB unavailable should not crash the agent."""
        agent = self._make_agent()
        agent._llm.complete = AsyncMock(return_value=MagicMock(content='{"accuracy_grade":"B","lessons_learned":[],"model_improvements":[],"drift_detected":false,"summary":"ok"}'))
        with patch("app.mcp_servers.history_server.store_event_outcome", side_effect=Exception("chromadb down")):
            db = _make_db_session()
            out = await agent.run(self._make_input(), db, exec_id="x7", event_id=EVENT_ID)

        assert out["stored_in_chroma"] is False
        assert out["chroma_error"] is not None

    def test_default_analysis_grades_correctly(self):
        from app.agents.learning import LearningAgent
        agent = LearningAgent()
        assert agent._default_analysis(2.0, 3.0)["accuracy_grade"] == "A"
        assert agent._default_analysis(7.0, 3.0)["accuracy_grade"] == "B"
        assert agent._default_analysis(15.0, 3.0)["accuracy_grade"] == "C"
        assert agent._default_analysis(25.0, 3.0)["accuracy_grade"] == "D"

    def test_default_analysis_drift_detection(self):
        from app.agents.learning import LearningAgent
        agent = LearningAgent()
        assert agent._default_analysis(20.0, 5.0)["drift_detected"] is True
        assert agent._default_analysis(5.0, 5.0)["drift_detected"] is False
