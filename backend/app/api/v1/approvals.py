"""
Human approval workflow endpoints — M4 real implementation.

Endpoints:
  GET  /api/v1/approvals/              List pending/recent action plans
  GET  /api/v1/approvals/plans/{id}    Get full plan detail
  POST /api/v1/approvals/plans/{id}/approve   Officer approves
  POST /api/v1/approvals/plans/{id}/reject    Officer rejects
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DBSession
from app.models.db.action_plan import ActionPlan
from app.models.db.action_plan_approval import ActionPlanApproval
from app.models.db.base import new_uuid
from app.models.db.orchestrator_session import OrchestratorSession

router = APIRouter()
log = structlog.get_logger(__name__)


# ── Request models ────────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    officer_id: str
    comments: str = ""
    session_id: str | None = None    # for LangGraph resume


class RejectRequest(BaseModel):
    officer_id: str
    comments: str = ""
    session_id: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_pending_approvals(db: DBSession) -> dict:
    """List action plans awaiting approval or recently decided."""
    result = await db.execute(
        select(ActionPlan)
        .where(ActionPlan.status.in_(["PENDING_APPROVAL", "APPROVED", "REJECTED"]))
        .order_by(ActionPlan.created_at.desc())
        .limit(50)
    )
    plans = result.scalars().all()

    return {
        "plans": [
            {
                "id": p.id,
                "event_id": p.event_id,
                "session_id": p.session_id,
                "status": p.status,
                "summary": p.summary,
                "confidence_score": float(p.confidence_score) if p.confidence_score else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans
        ],
        "pending_count": sum(1 for p in plans if p.status == "PENDING_APPROVAL"),
    }


@router.get("/plans/{plan_id}")
async def get_plan_detail(plan_id: str, db: DBSession) -> dict:
    """Return full action plan content for officer review."""
    result = await db.execute(select(ActionPlan).where(ActionPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, detail="Plan not found")

    return {
        "id": plan.id,
        "event_id": plan.event_id,
        "session_id": plan.session_id,
        "status": plan.status,
        "version": plan.version,
        "summary": plan.summary,
        "strategies_considered": plan.strategies_considered,
        "recommended_strategy": plan.recommended_strategy,
        "metro_actions": plan.metro_actions,
        "bmtc_actions": plan.bmtc_actions,
        "auto_actions": plan.auto_actions,
        "police_actions": plan.police_actions,
        "citizen_guidance": plan.citizen_guidance,
        "risk_assessment": plan.risk_assessment,
        "confidence_score": float(plan.confidence_score) if plan.confidence_score else None,
        "data_source_summary": plan.data_source_summary,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


@router.post("/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    body: ApprovalRequest,
    db: DBSession,
    request: Request,
) -> dict:
    """
    Officer approves an action plan.

    Updates plan status, creates approval record, resumes LangGraph pipeline.
    """
    # Load plan
    result = await db.execute(select(ActionPlan).where(ActionPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, detail="Plan not found")
    if plan.status != "PENDING_APPROVAL":
        raise HTTPException(409, detail=f"Plan is not pending approval (status={plan.status})")

    # Update plan status
    plan.status = "APPROVED"
    await db.flush()

    # Create approval record
    approval = ActionPlanApproval(
        id=str(new_uuid()),
        plan_id=plan_id,
        officer_id=body.officer_id,
        decision="APPROVED",
        comments=body.comments,
        ip_address=request.client.host if request.client else None,
    )
    db.add(approval)
    await db.flush()

    # Update orchestrator session approval status
    await db.execute(
        update(OrchestratorSession)
        .where(OrchestratorSession.id == plan.session_id)
        .values(approval_status="APPROVED")
    )
    await db.flush()

    log.info("approval.plan_approved", plan_id=plan_id, officer=body.officer_id)

    # Resume LangGraph pipeline if session_id provided
    session_id = body.session_id or plan.session_id
    resumed = False
    try:
        from app.orchestrator.runner import get_runner  # noqa: PLC0415
        from app.dependencies import _session_factory  # noqa: PLC0415
        runner = get_runner(_session_factory)
        if runner:
            import asyncio  # noqa: PLC0415
            asyncio.create_task(
                runner.resume_with_approval(
                    session_id=session_id,
                    decision="APPROVED",
                    officer_id=body.officer_id,
                    comments=body.comments,
                )
            )
            resumed = True
    except Exception as exc:
        log.warning("approval.resume_failed", error=str(exc))

    return {
        "status": "approved",
        "plan_id": plan_id,
        "session_id": session_id,
        "officer_id": body.officer_id,
        "pipeline_resumed": resumed,
        "message": "Plan approved. Citizen guidance and learning phases will execute.",
    }


@router.post("/plans/{plan_id}/reject")
async def reject_plan(
    plan_id: str,
    body: RejectRequest,
    db: DBSession,
    request: Request,
) -> dict:
    """
    Officer rejects an action plan.

    Updates plan status, creates rejection record, terminates pipeline.
    """
    result = await db.execute(select(ActionPlan).where(ActionPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, detail="Plan not found")
    if plan.status != "PENDING_APPROVAL":
        raise HTTPException(409, detail=f"Plan is not pending approval (status={plan.status})")

    plan.status = "REJECTED"
    await db.flush()

    approval = ActionPlanApproval(
        id=str(new_uuid()),
        plan_id=plan_id,
        officer_id=body.officer_id,
        decision="REJECTED",
        comments=body.comments,
        ip_address=request.client.host if request.client else None,
    )
    db.add(approval)
    await db.flush()

    await db.execute(
        update(OrchestratorSession)
        .where(OrchestratorSession.id == plan.session_id)
        .values(approval_status="REJECTED", status="REJECTED")
    )
    await db.flush()

    log.info("approval.plan_rejected", plan_id=plan_id, officer=body.officer_id)

    # Resume LangGraph pipeline with REJECTED decision (pipeline will terminate)
    session_id = body.session_id or plan.session_id
    try:
        from app.orchestrator.runner import get_runner  # noqa: PLC0415
        from app.dependencies import _session_factory  # noqa: PLC0415
        runner = get_runner(_session_factory)
        if runner:
            import asyncio  # noqa: PLC0415
            asyncio.create_task(
                runner.resume_with_approval(
                    session_id=session_id,
                    decision="REJECTED",
                    officer_id=body.officer_id,
                    comments=body.comments,
                )
            )
    except Exception as exc:
        log.warning("approval.reject_resume_failed", error=str(exc))

    return {
        "status": "rejected",
        "plan_id": plan_id,
        "session_id": session_id,
        "officer_id": body.officer_id,
        "message": "Plan rejected. Pipeline terminated.",
    }


@router.post("/plans/{plan_id}/send-back")
async def send_back_plan(plan_id: str) -> dict:
    # SEND_BACK deferred to post-hackathon
    return {"status": "not_implemented", "detail": "SEND_BACK deferred to post-MVP"}
