"""AuditLog ORM model — table: audit_logs."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # NULL for system/agent actions
    actor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )

    # user | agent | system
    actor_type: Mapped[str] = mapped_column(String, default="user", nullable=False)

    # e.g. "APPROVE_PLAN", "TRIGGER_RUN", "AGENT_FAILED"
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # e.g. "action_plans"
    resource: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)

    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)

    # OpenTelemetry trace ID for cross-correlation
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # NOTE: PARTITION BY RANGE deferred — apply in a future migration at >1M rows
