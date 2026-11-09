"""OrchestratorSession ORM model — table: orchestrator_sessions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class OrchestratorSession(Base):
    __tablename__ = "orchestrator_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )

    # RUNNING | COMPLETED | REJECTED | FAILED | TIMEOUT
    status: Mapped[str] = mapped_column(
        String, default="RUNNING", nullable=False, index=True
    )

    triggered_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )

    # MANUAL | REPLAY | SCHEDULED
    trigger_type: Mapped[str] = mapped_column(String, default="MANUAL", nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Which phase failed (if status = FAILED)
    failed_phase: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PENDING_APPROVAL | APPROVED | REJECTED | NULL
    approval_status: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    event = relationship("Event", back_populates="orchestrator_sessions")
    agent_executions = relationship("AgentExecution", back_populates="session")
    action_plans = relationship("ActionPlan", back_populates="session")
