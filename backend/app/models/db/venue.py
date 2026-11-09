"""Venue ORM model — table: venues."""

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False, default="Bengaluru")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PostGIS GEOGRAPHY(POINT, 4326) — use WKT "POINT(lon lat)" when inserting
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )

    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    # JSONB fields — arrays of gate / station / stop objects
    gates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metro_stations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bus_stops: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # H3 cell ID at resolution 7 for the venue center
    h3_center_res7: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    events = relationship("Event", back_populates="venue")
