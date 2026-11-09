"""
MCP Server 1 — Event Information Server (in-process).

Reads event and venue data from PostgreSQL via SQLAlchemy AsyncSession.
All functions are async — they require an active database session.

Promotion path: wrap each function in @mcp.tool() for Streamable HTTP MCP.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

async def get_event_details(event_id: str, db: "AsyncSession") -> dict | None:
    """
    Return structured event metadata for `event_id`.

    Parameters
    ----------
    event_id  UUID string of the event.
    db        Active AsyncSession.

    Returns
    -------
    Event details dict, or None if not found.
    """
    # Import inside function — avoids geoalchemy2 at module level in non-Docker environments
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.db.event import Event  # noqa: PLC0415
    from app.models.db.venue import Venue  # noqa: PLC0415

    stmt = (
        select(Event, Venue)
        .join(Venue, Event.venue_id == Venue.id)
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        return None

    event, venue = row

    return {
        "event_id": event.id,
        "name": event.name,
        "event_type": event.event_type,
        "venue_id": event.venue_id,
        "venue_name": venue.name,
        "estimated_attendance": event.estimated_attendance,
        "scheduled_start": event.scheduled_start.isoformat() if event.scheduled_start else None,
        "scheduled_end": event.scheduled_end.isoformat() if event.scheduled_end else None,
        "estimated_end": event.estimated_end.isoformat() if event.estimated_end else None,
        "status": event.status,
        "data_source": event.data_source,
        "metadata": event.metadata_ or {},
    }


async def list_upcoming_events(
    venue_id: str,
    date_from: datetime,
    date_to: datetime,
    db: "AsyncSession",
) -> list[dict]:
    """
    Return events at `venue_id` scheduled within [date_from, date_to].

    Parameters
    ----------
    venue_id   UUID string of the venue.
    date_from  Start of date range (inclusive).
    date_to    End of date range (inclusive).
    db         Active AsyncSession.

    Returns
    -------
    List of event summary dicts, ordered by scheduled_end ascending.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.db.event import Event  # noqa: PLC0415

    stmt = (
        select(Event)
        .where(Event.venue_id == venue_id)
        .where(Event.scheduled_end >= date_from)
        .where(Event.scheduled_end <= date_to)
        .order_by(Event.scheduled_end.asc())
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    return [
        {
            "event_id": e.id,
            "name": e.name,
            "event_type": e.event_type,
            "scheduled_start": e.scheduled_start.isoformat() if e.scheduled_start else None,
            "scheduled_end": e.scheduled_end.isoformat() if e.scheduled_end else None,
            "estimated_attendance": e.estimated_attendance,
            "status": e.status,
            "data_source": e.data_source,
        }
        for e in events
    ]


async def get_venue_layout(venue_id: str, db: "AsyncSession") -> dict | None:
    """
    Return gate positions, metro stations, bus stops, and capacity for `venue_id`.

    Parameters
    ----------
    venue_id  UUID string of the venue.
    db        Active AsyncSession.

    Returns
    -------
    Venue layout dict, or None if not found.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.db.venue import Venue  # noqa: PLC0415

    stmt = select(Venue).where(Venue.id == venue_id)
    result = await db.execute(stmt)
    venue = result.scalar_one_or_none()
    if venue is None:
        return None

    return {
        "venue_id": venue.id,
        "name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "total_capacity": venue.total_capacity,
        "h3_center_res7": venue.h3_center_res7,
        "gates": venue.gates or [],
        "metro_stations": venue.metro_stations or [],
        "bus_stops": venue.bus_stops or [],
    }
