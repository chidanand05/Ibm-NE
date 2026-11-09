"""AgentMessage ORM model — table: agent_messages."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # References orchestrator_sessions.id (no FK constraint for performance at scale)
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False, index=True
    )

    from_agent: Mapped[str] = mapped_column(String, nullable=False)  # "supervisor" or agent_id
    to_agent: Mapped[str] = mapped_column(String, nullable=False)

    # task_assignment | result | error
    message_type: Mapped[str] = mapped_column(String, nullable=False)

    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Ordering within session
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
