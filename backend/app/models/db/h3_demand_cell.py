"""H3DemandCell ORM model — table: h3_demand_cells."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base


class H3DemandCell(Base):
    __tablename__ = "h3_demand_cells"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forecast_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("crowd_forecasts.id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("events.id"), nullable=False
    )

    # H3 cell index string, e.g. "87194ad3fffffff"
    h3_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    resolution: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    center_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    demand_persons: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # LOW | MEDIUM | HIGH | CRITICAL
    demand_category: Mapped[str | None] = mapped_column(String, nullable=True)

    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source: Mapped[str] = mapped_column(String, default="SIMULATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    forecast = relationship("CrowdForecast", back_populates="h3_demand_cells")
