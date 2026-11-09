"""TransportSupplySnapshot ORM model — table: transport_supply_snapshots."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class TransportSupplySnapshot(Base):
    __tablename__ = "transport_supply_snapshots"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )
    agent_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )

    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_horizon: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes from event end

    # METRO | BMTC | AUTO | TAXI
    mode: Mapped[str] = mapped_column(String, nullable=False, index=True)

    h3_id: Mapped[str | None] = mapped_column(String, nullable=True)  # zone served
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)    # persons per hour
    vehicles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequency_mins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operational: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # demand - supply; negative = surplus
    gap_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)

    data_source: Mapped[str] = mapped_column(String, default="SIMULATED", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    event = relationship("Event", back_populates="transport_supply_snapshots")
