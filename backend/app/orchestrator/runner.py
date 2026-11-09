"""
Orchestrator session runner.

Creates an OrchestratorSession DB row, initialises the LangGraph pipeline,
runs it to the human-approval interrupt, and exposes a `resume_with_approval()`
method to continue execution after officer decision.

Usage
-----
    runner = OrchestratorRunner(session_maker)
    session_id = await runner.start(event_id="...", event_data={...})

    # Later, when officer approves:
    await runner.resume_with_approval(session_id, decision="APPROVED", officer_id="...")
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db.action_plan import ActionPlan
from app.models.db.orchestrator_session import OrchestratorSession
from app.orchestrator.state import ExodusState
from app.seed.constants import CHINNASWAMY_GATES, CHINNASWAMY_LAT, CHINNASWAMY_LON

log = structlog.get_logger(__name__)

# Module-level graph singleton (built once per process)
_graph = None


def _get_graph(session_maker):
    global _graph
    if _graph is None:
        from app.orchestrator.graph import build_graph  # noqa: PLC0415
        _graph = build_graph(db_factory=session_maker)
    return _graph


class OrchestratorRunner:
    """Manages LangGraph pipeline lifecycle for one or more event sessions."""

    def __init__(self, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            from app.orchestrator.graph import build_graph  # noqa: PLC0415
            self._graph = build_graph(db_factory=self._session_maker)
        return self._graph

    async def start(
        self,
        event_id: str,
        event_data: dict[str, Any],
        trigger_type: str = "MANUAL",
        triggered_by: str | None = None,
    ) -> str:
        """
        Create a new orchestrator session and start the pipeline.

        Returns the session_id (UUID string).
        The pipeline runs to the human_approval interrupt and suspends.
        """
        session_id = str(uuid.uuid4())

        # ── Create DB session row ─────────────────────────────────────────
        async with self._session_maker() as db:
            orch_session = OrchestratorSession(
                id=session_id,
                event_id=event_id,
                status="RUNNING",
                trigger_type=trigger_type,
                triggered_by=triggered_by,
                started_at=datetime.now(tz=timezone.utc),
                approval_status="PENDING_APPROVAL",
            )
            db.add(orch_session)
            await db.commit()

        # ── Build initial state ───────────────────────────────────────────
        initial_state: ExodusState = {
            "session_id": session_id,
            "event_id": event_id,
            "trigger_type": trigger_type,
            "event_name": event_data.get("event_name", "IPL Match"),
            "attendance": int(event_data.get("attendance", 30000)),
            "venue_lat": float(event_data.get("venue_lat", CHINNASWAMY_LAT)),
            "venue_lon": float(event_data.get("venue_lon", CHINNASWAMY_LON)),
            "gates": event_data.get("gates", CHINNASWAMY_GATES),
            "current_phase": "event_intel",
            "completed": False,
            "pipeline_version": "1.0",
            "approval_status": None,
            "approval_decision": None,
            "plan_id": None,
        }

        log.info("runner.starting", session_id=session_id, event_id=event_id)

        # ── Run graph to interrupt ────────────────────────────────────────
        try:
            config = {"configurable": {"thread_id": session_id}}
            await self.graph.ainvoke(initial_state, config=config)
        except Exception as exc:
            log.error("runner.graph_failed", session_id=session_id, error=str(exc))
            await self._mark_failed(session_id, str(exc))
            raise

        log.info("runner.suspended_at_approval", session_id=session_id)
        return session_id

    async def resume_with_approval(
        self,
        session_id: str,
        decision: str,            # APPROVED | REJECTED
        officer_id: str,
        comments: str = "",
    ) -> dict[str, Any]:
        """
        Resume the suspended graph after human approval.

        Returns the final state dict.
        """
        from langgraph.types import Command  # noqa: PLC0415

        config = {"configurable": {"thread_id": session_id}}
        resume_payload = {
            "decision": decision,
            "approved_by": officer_id,
            "comments": comments,
        }

        log.info(
            "runner.resuming",
            session_id=session_id,
            decision=decision,
            officer=officer_id,
        )

        try:
            final_state = await self.graph.ainvoke(
                Command(resume=resume_payload),
                config=config,
            )
        except Exception as exc:
            log.error("runner.resume_failed", session_id=session_id, error=str(exc))
            await self._mark_failed(session_id, str(exc))
            raise

        # ── Update orchestrator session status ────────────────────────────
        final_status = "COMPLETED" if decision == "APPROVED" else "REJECTED"
        async with self._session_maker() as db:
            await db.execute(
                update(OrchestratorSession)
                .where(OrchestratorSession.id == session_id)
                .values(
                    status=final_status,
                    approval_status=decision,
                    completed_at=datetime.now(tz=timezone.utc),
                )
            )
            await db.commit()

        log.info("runner.completed", session_id=session_id, status=final_status)
        return final_state

    async def get_session_state(self, session_id: str) -> dict | None:
        """Return current graph state snapshot for a session."""
        config = {"configurable": {"thread_id": session_id}}
        try:
            snapshot = await self.graph.aget_state(config)
            return dict(snapshot.values) if snapshot else None
        except Exception:
            return None

    async def _mark_failed(self, session_id: str, error: str) -> None:
        """Mark the orchestrator session as FAILED in DB."""
        try:
            async with self._session_maker() as db:
                await db.execute(
                    update(OrchestratorSession)
                    .where(OrchestratorSession.id == session_id)
                    .values(
                        status="FAILED",
                        error_message=error[:500],
                        completed_at=datetime.now(tz=timezone.utc),
                    )
                )
                await db.commit()
        except Exception:
            pass  # DB also down — log only


# ── Module-level singleton ────────────────────────────────────────────────────

_runner: OrchestratorRunner | None = None


def get_runner(session_maker: async_sessionmaker | None = None) -> OrchestratorRunner:
    """
    Return or create the module-level OrchestratorRunner.

    For FastAPI endpoints: pass session_maker on first call.
    For tests: create a new runner with a mock session_maker.
    """
    global _runner
    if _runner is None:
        if session_maker is None:
            from app.dependencies import _session_factory  # noqa: PLC0415
            session_maker = _session_factory
        _runner = OrchestratorRunner(session_maker)
    return _runner
