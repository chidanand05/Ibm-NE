"""ModelConfig ORM model — table: model_configs."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)

    # e.g. "event_intelligence", "planner"
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # planning | classification | generation
    task_type: Mapped[str] = mapped_column(String, nullable=False)

    model_name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)

    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    # e.g. "v1.0"
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)

    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0.1, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    creator = relationship("User", back_populates="model_configs")
