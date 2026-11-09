"""
Citizen Guidance API endpoints — M6.

Endpoints:
  GET  /api/v1/guidance/{session_id}          Get guidance for approved session
  GET  /api/v1/guidance/{session_id}/gate/{gate_id}   Gate-specific guidance
  POST /api/v1/guidance/generate              Generate guidance for an event (no session needed)
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.seed.constants import CHINNASWAMY_GATES, RCB_EVENT_ID

router = APIRouter()
log = structlog.get_logger(__name__)


# ── Request models ────────────────────────────────────────────────────────────

class GuidanceGenerateRequest(BaseModel):
    event_id: str = RCB_EVENT_ID
    event_name: str = "RCB vs CSK IPL 2026"
    attendance: int = 30000
    priority_mode: str = "METRO"
    gate_sequence: list[dict] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{session_id}")
async def get_session_guidance(session_id: str) -> dict:
    """Return citizen guidance for an approved orchestrator session."""
    runner = _get_runner()
    if runner is None:
        raise HTTPException(503, detail="Orchestrator unavailable")

    try:
        state = await runner.get_session_state(session_id)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))

    if not state:
        raise HTTPException(404, detail="Session not found")

    guidance = state.get("citizen_guidance", {})
    if not guidance:
        approval = state.get("approval_decision", "")
        if approval != "APPROVED":
            raise HTTPException(
                409,
                detail=f"Guidance not yet available. Session approval status: {approval or 'PENDING'}",
            )
        raise HTTPException(404, detail="Guidance not yet generated for this session")

    return {
        "session_id": session_id,
        "event_id": state.get("event_id"),
        "event_name": guidance.get("event_name"),
        "general_guidance": guidance.get("general_guidance", {}),
        "metro_instructions": guidance.get("metro_instructions", {}),
        "safety_message": guidance.get("safety_message", {}),
        "guidance_by_gate": guidance.get("guidance_by_gate", {}),
        "gate_sequence": guidance.get("gate_sequence", []),
        "priority_mode": guidance.get("priority_mode", "METRO"),
        "languages": guidance.get("languages", ["english", "kannada", "hindi"]),
        "llm_fallback": guidance.get("llm_fallback", False),
        "data_source": "SIMULATED",
    }


@router.get("/{session_id}/gate/{gate_id}")
async def get_gate_guidance(session_id: str, gate_id: str) -> dict:
    """Return gate-specific guidance in all languages."""
    runner = _get_runner()
    state = None
    if runner:
        try:
            state = await runner.get_session_state(session_id)
        except Exception:
            pass

    if not state:
        raise HTTPException(404, detail="Session not found")

    guidance = state.get("citizen_guidance", {})
    by_gate = guidance.get("guidance_by_gate", {})
    gate_upper = gate_id.upper()

    if gate_upper not in by_gate:
        raise HTTPException(
            404,
            detail=f"Gate {gate_id} not found. Available: {list(by_gate.keys())}",
        )

    return {
        "session_id": session_id,
        "gate_id": gate_upper,
        "guidance": by_gate[gate_upper],
        "languages": ["english", "kannada", "hindi"],
    }


@router.post("/generate")
async def generate_guidance(request: GuidanceGenerateRequest) -> dict:
    """
    Generate guidance synchronously without a full session.
    Uses CitizenGuidanceAgent directly with LLM (fallback-safe).
    """
    from unittest.mock import AsyncMock as _AsyncMock  # noqa: PLC0415
    from app.agents.citizen_guidance import CitizenGuidanceAgent  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    gate_sequence = request.gate_sequence or [
        {"gate_id": g["gate_id"], "delay_minutes": i * 5}
        for i, g in enumerate(CHINNASWAMY_GATES)
    ]

    input_data = {
        "event_id": request.event_id,
        "event_intelligence": {"event_name": request.event_name},
        "planner": {
            "gate_release_sequence": gate_sequence,
            "metro_actions": ["Activate Purple Line surge: 6 trains/hour"],
            "bmtc_actions": ["Deploy 6 buses at KG Road Junction"],
        },
        "supply": {"priority_mode": request.priority_mode},
    }

    # Use a dummy DB session (no DB write needed for standalone generation)
    db = _AsyncMock()
    db.add = lambda *a: None
    db.flush = _AsyncMock()

    agent = CitizenGuidanceAgent()
    session_id = str(uuid.uuid4())

    try:
        result = await agent.execute(input_data, db, session_id, request.event_id)
    except Exception as exc:
        log.error("guidance.generate_failed", error=str(exc))
        raise HTTPException(500, detail=str(exc))

    return {
        "event_id": request.event_id,
        "event_name": request.event_name,
        "general_guidance": result.get("general_guidance", {}),
        "metro_instructions": result.get("metro_instructions", {}),
        "safety_message": result.get("safety_message", {}),
        "guidance_by_gate": result.get("guidance_by_gate", {}),
        "gate_sequence": gate_sequence,
        "priority_mode": request.priority_mode,
        "languages": ["english", "kannada", "hindi"],
        "llm_fallback": result.get("llm_fallback", False),
        "data_source": "SIMULATED",
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_runner():
    try:
        from app.orchestrator.runner import get_runner  # noqa: PLC0415
        from app.dependencies import _session_factory  # noqa: PLC0415
        return get_runner(_session_factory)
    except Exception:
        return None
