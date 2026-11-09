"""HistoricalOutcome ORM model — table: historical_outcomes."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class HistoricalOutcome(Base):
    __tablename__ = "historical_outcomes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )
    plan_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("action_plans.id"), nullable=True
    )

    recorded_by: Mapped[str] = mapped_column(String, default="learning_agent", nullable=False)

    actual_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_exit_duration_mins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_peak_zone_h3: Mapped[str | None] = mapped_column(String, nullable=True)

    # Mean absolute error of demand forecast
    forecast_mae: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    forecast_error_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ADEQUATE | INADEQUATE | EXCESS
    transport_adequacy: Mapped[str | None] = mapped_column(String, nullable=True)

    # EFFECTIVE | PARTIAL | INEFFECTIVE | UNKNOWN
    plan_effectiveness: Mapped[str | None] = mapped_column(String, nullable=True)

    lessons_learned: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reference to ChromaDB document for RAG
    chroma_doc_id: Mapped[str | None] = mapped_column(String, nullable=True)

    data_source: Mapped[str] = mapped_column(String, default="SIMULATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    event = relationship("Event", back_populates="historical_outcomes")
    plan = relationship("ActionPlan", back_populates="historical_outcomes")
