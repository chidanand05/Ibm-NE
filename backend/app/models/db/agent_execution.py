"""AgentExecution ORM model — table: agent_executions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orchestrator_sessions.id"),
        nullable=False,
        index=True,
    )

    # e.g. "event_intelligence", "egress_forecast"
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_version: Mapped[str] = mapped_column(String, default="1.0", nullable=False)

    # PENDING | RUNNING | COMPLETED | FAILED | TIMEOUT
    status: Mapped[str] = mapped_column(
        String, default="PENDING", nullable=False, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # e.g. "watsonx/ibm/granite-3-1-8b-instruct"
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    event = relationship("Event", back_populates="agent_executions")
    session = relationship("OrchestratorSession", back_populates="agent_executions")
    llm_usage_records = relationship("LLMUsage", back_populates="agent_execution")
