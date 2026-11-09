"""Event ORM model — table: events."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    venue_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("venues.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # cricket, concert, etc.
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    estimated_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # SCHEDULED | ACTIVE | ENDED | ARCHIVED
    status: Mapped[str] = mapped_column(String, default="SCHEDULED", nullable=False, index=True)

    # REAL | SIMULATED
    data_source: Mapped[str] = mapped_column(String, default="SIMULATED", nullable=False)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    venue = relationship("Venue", back_populates="events")
    creator = relationship("User", back_populates="events", foreign_keys=[created_by])
    orchestrator_sessions = relationship("OrchestratorSession", back_populates="event")
    crowd_forecasts = relationship("CrowdForecast", back_populates="event")
    transport_supply_snapshots = relationship("TransportSupplySnapshot", back_populates="event")
    agent_executions = relationship("AgentExecution", back_populates="event")
    action_plans = relationship("ActionPlan", back_populates="event")
    historical_outcomes = relationship("HistoricalOutcome", back_populates="event")
