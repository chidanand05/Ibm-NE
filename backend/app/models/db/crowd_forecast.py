"""CrowdForecast ORM model — table: crowd_forecasts."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class CrowdForecast(Base):
    __tablename__ = "crowd_forecasts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False, index=True
    )
    agent_exec_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_executions.id"), nullable=True
    )

    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 20 or 40
    total_demand: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_zone_h3: Mapped[str | None] = mapped_column(String, nullable=True)

    # Confidence score 0.00–1.00
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    data_source: Mapped[str] = mapped_column(String, default="SIMULATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    event = relationship("Event", back_populates="crowd_forecasts")
    h3_demand_cells = relationship("H3DemandCell", back_populates="forecast")
