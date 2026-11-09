"""Venue seed — Chinnaswamy Stadium."""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.constants import (
    CHINNASWAMY_BUS_STOPS,
    CHINNASWAMY_GATES,
    CHINNASWAMY_LAT,
    CHINNASWAMY_LON,
    CHINNASWAMY_METRO_STATIONS,
    CHINNASWAMY_VENUE_ID,
)

log = structlog.get_logger(__name__)


async def seed_venue(db: AsyncSession) -> None:
    """Insert Chinnaswamy Stadium venue. Idempotent."""
    import json
    import h3 as _h3

    h3_center = _h3.latlng_to_cell(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)

    stmt = text("""
        INSERT INTO venues (id, name, city, address, location, total_capacity,
                           gates, metro_stations, bus_stops, h3_center_res7, created_at)
        VALUES (
            :id, :name, :city, :address,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
            :total_capacity,
            :gates::jsonb, :metro_stations::jsonb, :bus_stops::jsonb,
            :h3_center_res7, NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """)
    await db.execute(stmt, {
        "id":               CHINNASWAMY_VENUE_ID,
        "name":             "M. Chinnaswamy Stadium",
        "city":             "Bengaluru",
        "address":          "Mahatma Gandhi Road, Shivaji Nagar, Bengaluru, Karnataka 560001",
        "lat":              CHINNASWAMY_LAT,
        "lon":              CHINNASWAMY_LON,
        "total_capacity":   35_000,
        "gates":            json.dumps(CHINNASWAMY_GATES),
        "metro_stations":   json.dumps(CHINNASWAMY_METRO_STATIONS),
        "bus_stops":        json.dumps(CHINNASWAMY_BUS_STOPS),
        "h3_center_res7":   h3_center,
    })
    log.info("seed.venue_upserted", venue_id=CHINNASWAMY_VENUE_ID)
