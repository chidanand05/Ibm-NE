"""ActionPlan ORM model — table: action_plans."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class ActionPlan(Base):
    __tablename__ = "action_plans"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("orchestrator_sessions.id"), nullable=False, index=True
    )

    # PENDING_APPROVAL | APPROVED | REJECTED | SUPERSEDED
    status: Mapped[str] = mapped_column(
        String, default="PENDING_APPROVAL", nullable=False, index=True
    )

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_plan_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("action_plans.id"), nullable=True
    )

    # Agent execution references
    event_intel_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )
    forecast_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )
    supply_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )
    police_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )
    planner_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )
    guidance_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )

    # Plan content
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strategies_considered: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recommended_strategy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metro_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bmtc_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    auto_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    police_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    citizen_guidance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_assessment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    data_source_summary: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    event = relationship("Event", back_populates="action_plans")
    session = relationship("OrchestratorSession", back_populates="action_plans")
    approvals = relationship("ActionPlanApproval", back_populates="plan")
    historical_outcomes = relationship("HistoricalOutcome", back_populates="plan")
