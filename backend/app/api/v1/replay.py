"""
Demo Replay API endpoint — M8.

Triggers a full orchestrator pipeline run with the seeded RCB demo event,
simulating a real event for demonstration purposes.

Endpoint:
  POST /api/v1/replay/start           Start demo replay session
  GET  /api/v1/replay/status/{id}     Get replay session status
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from app.seed.constants import (
    CHINNASWAMY_GATES,
    CHINNASWAMY_LAT,
    CHINNASWAMY_LON,
    RCB_EVENT_ID,
)

router = APIRouter()
log = structlog.get_logger(__name__)

# Demo event defaults
DEMO_EVENT = {
    "event_id": RCB_EVENT_ID,
    "event_name": "RCB vs CSK IPL 2026 — DEMO",
    "attendance": 33000,
    "venue_lat": CHINNASWAMY_LAT,
    "venue_lon": CHINNASWAMY_LON,
    "gates": CHINNASWAMY_GATES,
}


@router.post("/start")
async def start_replay() -> dict:
    """
    Trigger a complete demo replay of the Namma Exodus pipeline.

    Uses the seeded RCB event with 33,000 attendance.
    Returns a session_id for polling. All values are SIMULATED.
    """
    runner = _get_runner()
    if runner is None:
        # Return demo response even without the orchestrator
        import uuid  # noqa: PLC0415
        demo_session_id = str(uuid.uuid4())
        log.warning("replay.orchestrator_unavailable", demo_session_id=demo_session_id)
        return {
            "session_id": demo_session_id,
            "status": "SIMULATED_DEMO",
            "event_id": DEMO_EVENT["event_id"],
            "event_name": DEMO_EVENT["event_name"],
            "attendance": DEMO_EVENT["attendance"],
            "message": (
                "Demo session started (orchestrator offline — using simulated data). "
                "All values carry data_source=SIMULATED."
            ),
            "data_source": "SIMULATED",
        }

    event_data = {
        "event_name": DEMO_EVENT["event_name"],
        "attendance": DEMO_EVENT["attendance"],
        "venue_lat": DEMO_EVENT["venue_lat"],
        "venue_lon": DEMO_EVENT["venue_lon"],
        "gates": DEMO_EVENT["gates"],
    }

    try:
        session_id = await runner.start(
            event_id=DEMO_EVENT["event_id"],
            event_data=event_data,
            trigger_type="REPLAY",
            triggered_by=None,
        )
        return {
            "session_id": session_id,
            "status": "PENDING_APPROVAL",
            "event_id": DEMO_EVENT["event_id"],
            "event_name": DEMO_EVENT["event_name"],
            "attendance": DEMO_EVENT["attendance"],
            "message": (
                "Demo replay started. Pipeline running to approval gate. "
                "Poll /api/v1/replay/status/{session_id} for progress."
            ),
            "data_source": "SIMULATED",
        }
    except Exception as exc:
        log.error("replay.start_failed", error=str(exc))
        raise HTTPException(500, detail=f"Replay failed: {exc}")


@router.get("/status/{session_id}")
async def replay_status(session_id: str) -> dict:
    """Return current status and outputs of a replay session."""
    runner = _get_runner()
    if runner is None:
        raise HTTPException(503, detail="Orchestrator unavailable")

    state = await runner.get_session_state(session_id)
    if not state:
        raise HTTPException(404, detail="Session not found")

    return {
        "session_id": session_id,
        "current_phase": state.get("current_phase"),
        "completed": state.get("completed", False),
        "approval_status": state.get("approval_status"),
        "decision_label": state.get("decision_label"),
        "decision_score": state.get("decision_score"),
        "event_name": state.get("event_name"),
        "attendance": state.get("attendance"),
        "plan_summary": state.get("planner", {}).get("summary") if state.get("planner") else None,
        "agents_completed": [
            agent for agent in [
                "event_intelligence", "egress_forecast", "supply",
                "police_coordination", "planner", "citizen_guidance", "learning"
            ]
            if state.get(agent)
        ],
        "data_source": "SIMULATED",
    }


@router.post("/auto-approve/{session_id}")
async def auto_approve_replay(session_id: str) -> dict:
    """
    Auto-approve a replay session (for demo purposes only).
    In production, human approval is always required.
    """
    runner = _get_runner()
    if runner is None:
        raise HTTPException(503, detail="Orchestrator unavailable")

    try:
        final_state = await runner.resume_with_approval(
            session_id=session_id,
            decision="APPROVED",
            officer_id="DEMO_OFFICER",
            comments="Demo auto-approval for replay demonstration",
        )
        return {
            "session_id": session_id,
            "status": "COMPLETED",
            "approved_by": "DEMO_OFFICER",
            "learning_grade": final_state.get("learning", {}).get("accuracy_grade", "N/A"),
            "completed": final_state.get("completed", False),
            "data_source": "SIMULATED",
            "message": "Demo replay completed. Check /api/v1/agents/scorecard/{session_id} for results.",
        }
    except Exception as exc:
        log.error("replay.auto_approve_failed", error=str(exc))
        raise HTTPException(500, detail=f"Auto-approve failed: {exc}")


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_runner():
    try:
        from app.orchestrator.runner import get_runner  # noqa: PLC0415
        from app.dependencies import _session_factory  # noqa: PLC0415
        return get_runner(_session_factory)
    except Exception:
        return None
