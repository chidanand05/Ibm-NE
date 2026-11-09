"""LLMUsage ORM model — table: llm_usage."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    agent_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True, index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=True, index=True
    )

    # e.g. "watsonx/ibm/granite-3-1-8b-instruct"
    model: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # watsonx | gemini | groq
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # SUCCESS | ERROR | TIMEOUT | FALLBACK_USED
    status: Mapped[str] = mapped_column(String, default="SUCCESS", nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    agent_execution = relationship("AgentExecution", back_populates="llm_usage_records")
