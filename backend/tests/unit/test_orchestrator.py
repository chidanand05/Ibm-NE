"""
Unit tests for M4 — Orchestrator (state, graph nodes, runner).

All DB operations and agent calls are mocked.
Tests focus on state transitions, routing logic, and runner lifecycle.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── ExodusState ────────────────────────────────────────────────────────────────

class TestExodusState:
    def test_state_typeddict_fields(self):
        from app.orchestrator.state import ExodusState
        state: ExodusState = {
            "session_id": "s1",
            "event_id": "e1",
            "trigger_type": "MANUAL",
            "event_name": "IPL Match",
            "attendance": 30000,
            "current_phase": "event_intel",
            "completed": False,
            "pipeline_version": "1.0",
        }
        assert state["session_id"] == "s1"
        assert state["attendance"] == 30000

    def test_merge_dict_reducer(self):
        from app.orchestrator.state import _merge_dict
        a = {"x": 1, "y": 2}
        b = {"y": 99, "z": 3}
        merged = _merge_dict(a, b)
        assert merged == {"x": 1, "y": 99, "z": 3}

    def test_merge_dict_none_safe(self):
        from app.orchestrator.state import _merge_dict
        assert _merge_dict(None, {"a": 1}) == {"a": 1}
        assert _merge_dict({"a": 1}, None) == {"a": 1}
        assert _merge_dict(None, None) == {}

    def test_last_reducer(self):
        from app.orchestrator.state import _last
        assert _last("old", "new") == "new"
        assert _last("old", None) == "old"
        assert _last(None, "new") == "new"


# ── Decision routing ──────────────────────────────────────────────────────────

class TestRouteAfterApproval:
    def test_routes_to_guidance_when_approved(self):
        from app.orchestrator.graph import route_after_approval
        from langgraph.graph import END
        state = {"approval_decision": "APPROVED"}
        result = route_after_approval(state)
        assert result == "citizen_guidance"

    def test_routes_to_end_when_rejected(self):
        from app.orchestrator.graph import route_after_approval
        from langgraph.graph import END
        state = {"approval_decision": "REJECTED"}
        result = route_after_approval(state)
        assert result == END

    def test_routes_to_end_when_missing(self):
        from app.orchestrator.graph import route_after_approval
        from langgraph.graph import END
        state = {}
        result = route_after_approval(state)
        assert result == END


# ── Graph nodes ────────────────────────────────────────────────────────────────

class TestGraphNodes:
    """Test each graph node in isolation with mocked agents."""

    BASE_STATE = {
        "session_id": "sess-1",
        "event_id": "20000000-0000-0000-0000-000000000001",
        "event_name": "RCB vs CSK",
        "attendance": 30000,
        "venue_lat": 12.9789,
        "venue_lon": 77.5996,
        "gates": [],
        "current_phase": "event_intel",
        "completed": False,
        "pipeline_version": "1.0",
    }

    @pytest.mark.asyncio
    async def test_node_event_intelligence_returns_state_update(self):
        from app.orchestrator.graph import node_event_intelligence

        mock_output = {
            "agent_id": "event_intelligence",
            "risk_level": "HIGH",
            "llm_fallback": False,
            "data_source": "SIMULATED",
            "exec_id": "exec-1",
        }

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.orchestrator.graph._broadcast", new=AsyncMock()):
            with patch("app.agents.event_intelligence.EventIntelligenceAgent.execute",
                       new=AsyncMock(return_value=mock_output)):
                result = await node_event_intelligence(self.BASE_STATE, db)

        assert result["current_phase"] == "parallel"
        assert result["event_intelligence"]["risk_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_node_parallel_agents_returns_three_outputs(self):
        from app.orchestrator.graph import node_parallel_agents

        ef_out = {"agent_id": "egress_forecast", "total_demand_20": 18000,
                  "total_demand_40": 27000, "llm_fallback": False, "exec_id": "e1"}
        sup_out = {"agent_id": "supply", "overall_gap_20": 5000,
                   "llm_fallback": False, "exec_id": "e2"}
        pol_out = {"agent_id": "police_coordination", "critical_roads": ["MG Road"],
                   "llm_fallback": False, "exec_id": "e3"}

        state = {**self.BASE_STATE, "event_intelligence": {"attendance": 30000, "gates": []}}
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.orchestrator.graph._broadcast", new=AsyncMock()):
            with patch("app.agents.egress_forecast.EgressForecastAgent.execute",
                       new=AsyncMock(return_value=ef_out)):
                with patch("app.agents.supply.SupplyAgent.execute",
                           new=AsyncMock(return_value=sup_out)):
                    with patch("app.agents.police_coordination.PoliceCoordinationAgent.execute",
                               new=AsyncMock(return_value=pol_out)):
                        result = await node_parallel_agents(state, db)

        assert result["current_phase"] == "planner"
        assert result["egress_forecast"]["total_demand_20"] == 18000
        assert "supply" in result
        assert "police_coordination" in result

    @pytest.mark.asyncio
    async def test_node_citizen_guidance_runs_after_approval(self):
        from app.orchestrator.graph import node_citizen_guidance

        guidance_out = {"agent_id": "citizen_guidance", "languages": ["english", "kannada", "hindi"],
                        "llm_fallback": False, "exec_id": "e6"}
        state = {
            **self.BASE_STATE,
            "event_intelligence": {},
            "planner": {"gate_release_sequence": []},
            "supply": {"priority_mode": "METRO"},
            "approval_decision": "APPROVED",
        }
        db = AsyncMock()

        with patch("app.orchestrator.graph._broadcast", new=AsyncMock()):
            with patch("app.agents.citizen_guidance.CitizenGuidanceAgent.execute",
                       new=AsyncMock(return_value=guidance_out)):
                result = await node_citizen_guidance(state, db)

        assert result["current_phase"] == "learning"
        assert result["citizen_guidance"]["languages"] == ["english", "kannada", "hindi"]

    @pytest.mark.asyncio
    async def test_node_learning_sets_completed(self):
        from app.orchestrator.graph import node_learning

        learning_out = {"agent_id": "learning", "accuracy_grade": "B",
                        "llm_fallback": False, "exec_id": "e7", "stored_in_chroma": True}
        state = {
            **self.BASE_STATE,
            "event_intelligence": {}, "egress_forecast": {}, "supply": {},
            "police_coordination": {}, "planner": {},
        }
        db = AsyncMock()

        with patch("app.orchestrator.graph._broadcast", new=AsyncMock()):
            with patch("app.agents.learning.LearningAgent.execute",
                       new=AsyncMock(return_value=learning_out)):
                result = await node_learning(state, db)

        assert result["completed"] is True
        assert result["current_phase"] == "done"


# ── OrchestratorRunner ────────────────────────────────────────────────────────

class TestOrchestratorRunner:
    def _make_session_maker(self):
        """Return a mock async_sessionmaker."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        maker = MagicMock()
        maker.return_value = session
        maker.__call__ = MagicMock(return_value=session)
        return maker

    def test_runner_instantiation(self):
        from app.orchestrator.runner import OrchestratorRunner
        maker = self._make_session_maker()
        runner = OrchestratorRunner(maker)
        assert runner._session_maker is maker

    def test_get_runner_returns_singleton(self):
        """get_runner returns same instance on multiple calls."""
        from app.orchestrator.runner import OrchestratorRunner
        import app.orchestrator.runner as runner_mod
        # Reset singleton
        runner_mod._runner = None
        maker = self._make_session_maker()
        r1 = OrchestratorRunner(maker)
        runner_mod._runner = r1
        r2 = runner_mod.get_runner()
        assert r1 is r2
        runner_mod._runner = None  # cleanup

    @pytest.mark.asyncio
    async def test_start_calls_graph_ainvoke(self):
        from app.orchestrator.runner import OrchestratorRunner
        maker = self._make_session_maker()

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})

        runner = OrchestratorRunner(maker)
        runner._graph = mock_graph

        with patch("app.orchestrator.runner.OrchestratorRunner._mark_failed", new=AsyncMock()):
            session_id = await runner.start(
                event_id="20000000-0000-0000-0000-000000000001",
                event_data={"event_name": "RCB vs CSK", "attendance": 30000},
            )

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        mock_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_with_approval_calls_command_invoke(self):
        from app.orchestrator.runner import OrchestratorRunner
        from langgraph.types import Command
        maker = self._make_session_maker()

        mock_graph = AsyncMock()
        final_state = {"completed": True, "approval_decision": "APPROVED"}
        mock_graph.ainvoke = AsyncMock(return_value=final_state)

        runner = OrchestratorRunner(maker)
        runner._graph = mock_graph

        result = await runner.resume_with_approval(
            session_id="sess-1",
            decision="APPROVED",
            officer_id="officer-1",
            comments="Looks good",
        )

        assert result["completed"] is True
        mock_graph.ainvoke.assert_called_once()
        # Check that Command was passed
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert isinstance(call_args, Command)
