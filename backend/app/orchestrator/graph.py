"""
LangGraph orchestrator graph for Namma Exodus.

Pipeline flow:
  event_intelligence
        │
  ┌─────┴──────────────────────┐
  egress_forecast  supply  police_coordination   ← asyncio.gather (parallel)
  └─────┬──────────────────────┘
        │
     planner
        │
   human_approval  ← LangGraph interrupt() — waits for officer decision
        │
   citizen_guidance
        │
      learning
        │
      [done]

Key design decisions:
- AsyncPostgresSaver used in Docker; MemorySaver used locally (import fallback).
- `interrupt()` suspends the graph so the HTTP endpoint can inject the approval.
- All agent node errors are caught inside BaseAgent.execute() — never bubble up.
- WebSocket fan-out happens inside each node after the agent completes.
"""

from __future__ import annotations

import asyncio
import structlog

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.citizen_guidance import CitizenGuidanceAgent
from app.agents.egress_forecast import EgressForecastAgent
from app.agents.event_intelligence import EventIntelligenceAgent
from app.agents.learning import LearningAgent
from app.agents.planner import PlannerAgent
from app.agents.police_coordination import PoliceCoordinationAgent
from app.agents.supply import SupplyAgent
from app.models.db.action_plan import ActionPlan
from app.models.db.base import new_uuid
from app.orchestrator.state import ExodusState
from app.services.decision_engine import score_plan

log = structlog.get_logger(__name__)

# ── LangGraph checkpointer (graceful fallback) ────────────────────────────────

def _get_checkpointer():
    """
    Try AsyncPostgresSaver (Docker). Fall back to MemorySaver locally.
    Returns the checkpointer instance (not yet connected to DB).
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: PLC0415
        from app.config import get_settings  # noqa: PLC0415
        settings = get_settings()
        # AsyncPostgresSaver requires explicit setup() call before use — done in runner.py
        return AsyncPostgresSaver.from_conn_string(settings.alembic_database_url)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver  # noqa: PLC0415
        return MemorySaver()


# ── WebSocket broadcast helper ────────────────────────────────────────────────

async def _broadcast(session_id: str, phase: str, payload: dict) -> None:
    """Fire-and-forget WebSocket broadcast; never raises."""
    try:
        from app.services.ws_broadcaster import broadcast  # noqa: PLC0415
        await broadcast(
            channel=f"session:{session_id}",
            message={"type": "agent_update", "phase": phase, "data": payload},
        )
    except Exception:
        pass  # WebSocket unavailable (local dev) — silently skip


# ── Node: event_intelligence ──────────────────────────────────────────────────

async def node_event_intelligence(state: ExodusState, db: AsyncSession) -> dict:
    agent = EventIntelligenceAgent()
    input_data = {
        "event_id": state["event_id"],
        "event_name": state.get("event_name", "IPL Match"),
        "attendance": state.get("attendance", 30000),
        "venue_lat": state.get("venue_lat", 12.9789),
        "venue_lon": state.get("venue_lon", 77.5996),
        "gates": state.get("gates", []),
    }
    result = await agent.execute(input_data, db, state["session_id"], state["event_id"])
    await _broadcast(state["session_id"], "event_intelligence", result)
    return {
        "event_intelligence": result,
        "current_phase": "parallel",
    }


# ── Node: parallel (gather egress + supply + police) ─────────────────────────

async def node_parallel_agents(state: ExodusState, db: AsyncSession) -> dict:
    """Run EgressForecast, Supply, and PoliceCoordination concurrently."""
    ei = state.get("event_intelligence", {})
    base_input = {
        "event_id": state["event_id"],
        "event_name": ei.get("event_name", state.get("event_name", "IPL Match")),
        "attendance": ei.get("attendance", state.get("attendance", 30000)),
        "venue_lat": ei.get("venue_lat", state.get("venue_lat", 12.9789)),
        "venue_lon": ei.get("venue_lon", state.get("venue_lon", 77.5996)),
        "gates": ei.get("gates", state.get("gates", [])),
    }

    ef_agent = EgressForecastAgent()
    sup_agent = SupplyAgent()
    pol_agent = PoliceCoordinationAgent()

    ef_out, sup_out, pol_out = await asyncio.gather(
        ef_agent.execute(base_input, db, state["session_id"], state["event_id"]),
        sup_agent.execute(
            {**base_input, "total_demand_20": 18000, "total_demand_40": 27000},
            db, state["session_id"], state["event_id"],
        ),
        pol_agent.execute(base_input, db, state["session_id"], state["event_id"]),
    )

    # Update supply input with actual forecast demand
    if not ef_out.get("llm_fallback"):
        sup_input = {
            **base_input,
            "total_demand_20": ef_out.get("total_demand_20", 18000),
            "total_demand_40": ef_out.get("total_demand_40", 27000),
        }
        sup_out = await sup_agent.execute(sup_input, db, state["session_id"], state["event_id"])

    await asyncio.gather(
        _broadcast(state["session_id"], "egress_forecast", ef_out),
        _broadcast(state["session_id"], "supply", sup_out),
        _broadcast(state["session_id"], "police_coordination", pol_out),
    )

    return {
        "egress_forecast": ef_out,
        "supply": sup_out,
        "police_coordination": pol_out,
        "current_phase": "planner",
    }


# ── Node: planner ─────────────────────────────────────────────────────────────

async def node_planner(state: ExodusState, db: AsyncSession) -> dict:
    agent = PlannerAgent()
    input_data = {
        "event_id": state["event_id"],
        "event_intelligence": state.get("event_intelligence", {}),
        "egress_forecast": state.get("egress_forecast", {}),
        "supply": state.get("supply", {}),
        "police_coordination": state.get("police_coordination", {}),
    }
    result = await agent.execute(input_data, db, state["session_id"], state["event_id"])

    # Compute decision score
    decision_score, decision_label = score_plan(result, state.get("egress_forecast", {}))

    # Persist ActionPlan row
    plan_id = str(new_uuid())
    plan = ActionPlan(
        id=plan_id,
        event_id=state["event_id"],
        session_id=state["session_id"],
        status="PENDING_APPROVAL",
        summary=result.get("summary", ""),
        strategies_considered=result.get("strategies_considered"),
        recommended_strategy=result.get("recommended_strategy"),
        metro_actions={"actions": result.get("metro_actions", [])},
        bmtc_actions={"actions": result.get("bmtc_actions", [])},
        auto_actions={"actions": result.get("auto_actions", [])},
        police_actions={"actions": result.get("police_actions", [])},
        risk_assessment=result.get("risk_assessment"),
        confidence_score=result.get("confidence_score"),
        data_source_summary="All transport data SIMULATED",
        planner_exec_id=result.get("exec_id"),
        event_intel_exec_id=state.get("event_intelligence", {}).get("exec_id"),
        forecast_exec_id=state.get("egress_forecast", {}).get("exec_id"),
        supply_exec_id=state.get("supply", {}).get("exec_id"),
        police_exec_id=state.get("police_coordination", {}).get("exec_id"),
    )
    db.add(plan)
    await db.flush()

    await _broadcast(state["session_id"], "planner", result)

    return {
        "planner": result,
        "plan_id": plan_id,
        "approval_status": "PENDING_APPROVAL",
        "decision_score": decision_score,
        "decision_label": decision_label,
        "current_phase": "approval",
    }


# ── Node: human_approval (LangGraph interrupt) ────────────────────────────────

async def node_human_approval(state: ExodusState, db: AsyncSession) -> dict:
    """
    Interrupt the graph and wait for a human officer's decision.

    The orchestrator runner calls graph.invoke() with the approval payload
    to resume execution. Until then, the graph is suspended here.
    """
    from langgraph.types import interrupt  # noqa: PLC0415

    log.info(
        "orchestrator.awaiting_approval",
        session_id=state["session_id"],
        plan_id=state.get("plan_id"),
    )

    # Suspend execution — resume when runner calls graph.invoke(Command(resume=...))
    decision = interrupt({
        "plan_id": state.get("plan_id"),
        "session_id": state["session_id"],
        "message": "Awaiting human officer approval",
        "plan_summary": state.get("planner", {}).get("summary", ""),
        "decision_label": state.get("decision_label", "AMBER"),
    })

    # `decision` is the payload passed via Command(resume=decision_payload)
    approval_decision = decision.get("decision", "REJECTED") if isinstance(decision, dict) else "REJECTED"
    comments = decision.get("comments", "") if isinstance(decision, dict) else ""
    approved_by = decision.get("approved_by", "") if isinstance(decision, dict) else ""

    # Update ActionPlan status in DB
    from sqlalchemy import select, update  # noqa: PLC0415
    await db.execute(
        update(ActionPlan)
        .where(ActionPlan.id == state.get("plan_id"))
        .values(status=approval_decision)
    )
    await db.flush()

    log.info(
        "orchestrator.approval_received",
        session_id=state["session_id"],
        decision=approval_decision,
    )

    return {
        "approval_decision": approval_decision,
        "approval_status": approval_decision,
        "approval_comments": comments,
        "approved_by": approved_by,
        "current_phase": "guidance" if approval_decision == "APPROVED" else "rejected",
    }


# ── Node: citizen_guidance ────────────────────────────────────────────────────

async def node_citizen_guidance(state: ExodusState, db: AsyncSession) -> dict:
    agent = CitizenGuidanceAgent()
    input_data = {
        "event_id": state["event_id"],
        "event_intelligence": state.get("event_intelligence", {}),
        "planner": state.get("planner", {}),
        "supply": state.get("supply", {}),
    }
    result = await agent.execute(input_data, db, state["session_id"], state["event_id"])
    await _broadcast(state["session_id"], "citizen_guidance", result)
    return {
        "citizen_guidance": result,
        "current_phase": "learning",
    }


# ── Node: learning ────────────────────────────────────────────────────────────

async def node_learning(state: ExodusState, db: AsyncSession) -> dict:
    agent = LearningAgent()
    input_data = {
        "event_id": state["event_id"],
        "event_intelligence": state.get("event_intelligence", {}),
        "egress_forecast": state.get("egress_forecast", {}),
        "supply": state.get("supply", {}),
        "police_coordination": state.get("police_coordination", {}),
        "planner": state.get("planner", {}),
    }
    result = await agent.execute(input_data, db, state["session_id"], state["event_id"])
    await _broadcast(state["session_id"], "learning", result)
    return {
        "learning": result,
        "current_phase": "done",
        "completed": True,
    }


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_approval(state: ExodusState) -> str:
    """Route to guidance if approved, else end."""
    if state.get("approval_decision") == "APPROVED":
        return "citizen_guidance"
    return END


# ── Graph factory ─────────────────────────────────────────────────────────────

def build_graph(db_factory=None):
    """
    Build and compile the Exodus StateGraph.

    Parameters
    ----------
    db_factory  Callable that returns an AsyncSession. Required for nodes that
                write to DB. When None (unit tests), nodes are wrapped to inject
                a mock session.
    """
    graph = StateGraph(ExodusState)

    # Wrap nodes to inject db session from factory
    def _wrap(node_fn):
        async def wrapped(state: ExodusState) -> dict:
            if db_factory is None:
                # Unit test mode — pass a dummy db
                return await node_fn(state, AsyncMock_())
            async with db_factory() as db:
                try:
                    result = await node_fn(state, db)
                    await db.commit()
                    return result
                except Exception:
                    await db.rollback()
                    raise
        return wrapped

    # Register nodes
    graph.add_node("event_intelligence", _wrap(node_event_intelligence))
    graph.add_node("parallel_agents", _wrap(node_parallel_agents))
    graph.add_node("planner", _wrap(node_planner))
    graph.add_node("human_approval", _wrap(node_human_approval))
    graph.add_node("citizen_guidance", _wrap(node_citizen_guidance))
    graph.add_node("learning", _wrap(node_learning))

    # Edges
    graph.set_entry_point("event_intelligence")
    graph.add_edge("event_intelligence", "parallel_agents")
    graph.add_edge("parallel_agents", "planner")
    graph.add_edge("planner", "human_approval")
    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {"citizen_guidance": "citizen_guidance", END: END},
    )
    graph.add_edge("citizen_guidance", "learning")
    graph.add_edge("learning", END)

    checkpointer = _get_checkpointer()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["human_approval"])


# ── Minimal async mock for unit test mode ─────────────────────────────────────

class AsyncMock_:
    """Minimal DB session stub for unit-test graph invocation."""
    def add(self, *a): pass
    async def flush(self): pass
    async def commit(self): pass
    async def rollback(self): pass
    async def execute(self, *a, **kw): return MagicMock_()
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass


class MagicMock_:
    def scalars(self): return self
    def all(self): return []
    def first(self): return None
