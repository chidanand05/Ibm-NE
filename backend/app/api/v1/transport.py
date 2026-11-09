"""Transport supply snapshot endpoints — Sub-task 2.1b."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import DBSession
from app.models.db.transport_supply_snapshot import TransportSupplySnapshot

from sqlalchemy import select

router = APIRouter()


@router.get("/")
async def list_transport_snapshots(
    db: DBSession,
    event_id: str | None = Query(None, description="Filter by event ID"),
    horizon: int | None = Query(None, description="Filter by time_horizon (20 or 40)"),
    mode: str | None = Query(None, description="Filter by mode: METRO|BMTC|AUTO|TAXI"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List transport supply snapshots, optionally filtered by event, horizon, and mode."""
    stmt = (
        select(TransportSupplySnapshot)
        .order_by(TransportSupplySnapshot.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if event_id:
        stmt = stmt.where(TransportSupplySnapshot.event_id == event_id)
    if horizon is not None:
        stmt = stmt.where(TransportSupplySnapshot.time_horizon == horizon)
    if mode:
        stmt = stmt.where(TransportSupplySnapshot.mode == mode.upper())
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return {
        "items": [_snapshot_to_dict(s) for s in snapshots],
        "total": len(snapshots),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{snapshot_id}")
async def get_transport_snapshot(snapshot_id: str, db: DBSession) -> dict:
    """Get a single transport supply snapshot."""
    stmt = select(TransportSupplySnapshot).where(TransportSupplySnapshot.id == snapshot_id)
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return _snapshot_to_dict(snapshot)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _snapshot_to_dict(s: TransportSupplySnapshot) -> dict:
    return {
        "snapshot_id":    s.id,
        "event_id":       s.event_id,
        "snapshot_time":  s.snapshot_time.isoformat() if s.snapshot_time else None,
        "time_horizon":   s.time_horizon,
        "mode":           s.mode,
        "capacity":       s.capacity,
        "vehicles":       s.vehicles,
        "frequency_mins": s.frequency_mins,
        "operational":    s.operational,
        "gap_persons":    s.gap_persons,
        "data_source":    s.data_source,
        "notes":          s.notes,
        "created_at":     s.created_at.isoformat() if s.created_at else None,
    }
