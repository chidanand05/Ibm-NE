"""
Agent execution endpoints — M4 real implementation.

Endpoints:
  GET  /api/v1/agents/                 List recent agent executions
  POST /api/v1/agents/run              Trigger orchestrator session
  GET  /api/v1/agents/sessions/{id}   Get session status + phase outputs
  GET  /api/v1/agents/scorecard/{id}  Get learning agent scorecard
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DBSession
from app.models.db.agent_execution import AgentExecution
from app.models.db.orchestrator_session import OrchestratorSession
from app.seed.constants import (
    CHINNASWAMY_GATES,
    CHINNASWAMY_LAT,
    CHINNASWAMY_LON,
    RCB_EVENT_ID,
)

router = APIRouter()
log = structlog.get_logger(__name__)


# ── Request / Response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    event_id: str = RCB_EVENT_ID
    event_name: str = "RCB vs CSK IPL 2026"
    attendance: int = 30000
    venue_lat: float = CHINNASWAMY_LAT
    venue_lon: float = CHINNASWAMY_LON
    gates: list[dict] = CHINNASWAMY_GATES
    trigger_type: str = "MANUAL"
    triggered_by: str | None = None


class RunResponse(BaseModel):
    session_id: str
    status: str
    message: str


# ── Helper: get runner lazily ─────────────────────────────────────────────────

def _get_runner(db_session):
    """Get OrchestratorRunner, initializing with current session factory."""
    try:
        from app.orchestrator.runner import get_runner  # noqa: PLC0415
        from app.dependencies import _session_factory  # noqa: PLC0415
        return get_runner(_session_factory)
    except Exception as exc:
        log.warning("agents.runner_unavailable", error=str(exc))
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_agent_executions(
    db: DBSession,
    session_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    """List recent agent executions with optional filters."""
    stmt = select(AgentExecution).order_by(AgentExecution.created_at.desc()).limit(limit)
    if session_id:
        stmt = stmt.where(AgentExecution.session_id == session_id)
    if agent_id:
        stmt = stmt.where(AgentExecution.agent_id == agent_id)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "executions": [
            {
                "id": r.id,
                "event_id": r.event_id,
                "session_id": r.session_id,
                "agent_id": r.agent_id,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "model_used": r.model_used,
                "llm_fallback": r.output_data.get("llm_fallback", False) if r.output_data else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.post("/run", response_model=RunResponse)
async def trigger_agent_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> RunResponse:
    """
    Trigger an orchestrator session for the given event.

    Runs the full pipeline in the background (event_intelligence → parallel agents
    → planner) and suspends at the human_approval interrupt.

    Returns the session_id immediately for polling.
    """
    runner = _get_runner(db)
    if runner is None:
        raise HTTPException(503, detail="Orchestrator unavailable — check LangGraph configuration")

    event_data = {
        "event_name": request.event_name,
        "attendance": request.attendance,
        "venue_lat": request.venue_lat,
        "venue_lon": request.venue_lon,
        "gates": request.gates,
    }

    async def _run_pipeline():
        try:
            await runner.start(
                event_id=request.event_id,
                event_data=event_data,
                trigger_type=request.trigger_type,
                triggered_by=request.triggered_by,
            )
        except Exception as exc:
            log.error("agents.pipeline_failed", error=str(exc))

    background_tasks.add_task(_run_pipeline)

    import uuid  # noqa: PLC0415
    placeholder_session_id = str(uuid.uuid4())

    return RunResponse(
        session_id=placeholder_session_id,
        status="STARTING",
        message="Pipeline started. Poll /api/v1/agents/sessions/{session_id} for status.",
    )


@router.post("/run-sync", response_model=RunResponse)
async def trigger_agent_run_sync(
    request: RunRequest,
    db: DBSession,
) -> RunResponse:
    """
    Trigger an orchestrator session synchronously (waits for approval interrupt).
    Returns session_id after pipeline reaches human_approval pause.
    """
    runner = _get_runner(db)
    if runner is None:
        raise HTTPException(503, detail="Orchestrator unavailable")

    event_data = {
        "event_name": request.event_name,
        "attendance": request.attendance,
        "venue_lat": request.venue_lat,
        "venue_lon": request.venue_lon,
        "gates": request.gates,
    }

    try:
        session_id = await runner.start(
            event_id=request.event_id,
            event_data=event_data,
            trigger_type=request.trigger_type,
            triggered_by=request.triggered_by,
        )
        return RunResponse(
            session_id=session_id,
            status="PENDING_APPROVAL",
            message="Pipeline reached approval gate. Awaiting officer decision.",
        )
    except Exception as exc:
        log.error("agents.run_sync_failed", error=str(exc))
        raise HTTPException(500, detail=f"Pipeline failed: {exc}")


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str, db: DBSession) -> dict:
    """Return current session status, phase outputs, and plan summary."""
    # DB session row
    result = await db.execute(
        select(OrchestratorSession).where(OrchestratorSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail="Session not found")

    # Agent executions for this session
    exec_result = await db.execute(
        select(AgentExecution)
        .where(AgentExecution.session_id == session_id)
        .order_by(AgentExecution.created_at)
    )
    executions = exec_result.scalars().all()

    # Try to get graph state snapshot
    runner = _get_runner(db)
    graph_state = None
    if runner:
        try:
            graph_state = await runner.get_session_state(session_id)
        except Exception:
            pass

    return {
        "session_id": session_id,
        "event_id": session.event_id,
        "status": session.status,
        "approval_status": session.approval_status,
        "trigger_type": session.trigger_type,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "agent_executions": [
            {
                "agent_id": e.agent_id,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "llm_fallback": e.output_data.get("llm_fallback") if e.output_data else None,
            }
            for e in executions
        ],
        "current_phase": graph_state.get("current_phase") if graph_state else session.status,
        "plan_summary": graph_state.get("planner", {}).get("summary") if graph_state else None,
        "decision_label": graph_state.get("decision_label") if graph_state else None,
    }


@router.get("/scorecard/{session_id}")
async def agent_scorecard(session_id: str, db: DBSession) -> dict:
    """Return learning agent scorecard for a completed session."""
    runner = _get_runner(db)
    graph_state = None
    if runner:
        try:
            graph_state = await runner.get_session_state(session_id)
        except Exception:
            pass

    if not graph_state:
        raise HTTPException(404, detail="Session state not found or session still running")

    learning = graph_state.get("learning", {})
    planner = graph_state.get("planner", {})
    egress = graph_state.get("egress_forecast", {})

    return {
        "session_id": session_id,
        "accuracy_metrics": learning.get("accuracy_metrics", {}),
        "accuracy_grade": learning.get("accuracy_grade", "N/A"),
        "lessons_learned": learning.get("lessons_learned", []),
        "model_improvements": learning.get("model_improvements", []),
        "drift_detected": learning.get("drift_detected", False),
        "confidence_score": planner.get("confidence_score"),
        "decision_label": graph_state.get("decision_label"),
        "decision_score": graph_state.get("decision_score"),
        "stored_in_chroma": learning.get("stored_in_chroma", False),
    }
