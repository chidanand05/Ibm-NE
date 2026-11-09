"""Event seed — RCB vs MI IPL 2027 demo event."""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.constants import CHINNASWAMY_VENUE_ID, RCB_EVENT_ID

log = structlog.get_logger(__name__)


async def seed_event(db: AsyncSession) -> None:
    """Insert RCB vs MI demo event. Idempotent."""
    import json

    stmt = text("""
        INSERT INTO events (id, venue_id, name, event_type,
                           scheduled_start, scheduled_end,
                           estimated_attendance, status, data_source, metadata, created_at, updated_at)
        VALUES (
            :id, :venue_id, :name, :event_type,
            :scheduled_start, :scheduled_end,
            :estimated_attendance, :status, :data_source, :metadata::jsonb,
            NOW(), NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """)
    await db.execute(stmt, {
        "id":                   RCB_EVENT_ID,
        "venue_id":             CHINNASWAMY_VENUE_ID,
        "name":                 "RCB vs MI — IPL 2027 (Simulated)",
        "event_type":           "cricket",
        "scheduled_start":      "2027-04-15 14:00:00+05:30",
        "scheduled_end":        "2027-04-15 17:30:00+05:30",
        "estimated_attendance": 34_000,
        "status":               "SCHEDULED",
        "data_source":          "SIMULATED",
        "metadata":             json.dumps({
            "home_team":    "Royal Challengers Bengaluru",
            "away_team":    "Mumbai Indians",
            "competition":  "IPL 2027",
            "note":         "This is a SIMULATED event for demonstration purposes only.",
        }),
    })
    log.info("seed.event_upserted", event_id=RCB_EVENT_ID)
