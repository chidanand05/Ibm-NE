"""Event management endpoints — Sub-task 2.1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text

from app.dependencies import DBSession
from app.models.db.event import Event
from app.models.db.venue import Venue

router = APIRouter()


@router.get("/")
async def list_events(
    db: DBSession,
    status: str | None = Query(None, description="Filter by status: SCHEDULED|ACTIVE|ENDED|ARCHIVED"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List events, optionally filtered by status."""
    stmt = select(Event).order_by(Event.scheduled_end.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Event.status == status.upper())
    result = await db.execute(stmt)
    events = result.scalars().all()
    return {
        "items": [_event_to_dict(e) for e in events],
        "total": len(events),
        "limit": limit,
        "offset": offset,
    }


@router.post("/", status_code=201)
async def create_event(body: dict, db: DBSession) -> dict:
    """Create a new event (officer/admin only — auth enforced in M4)."""
    from app.models.db.base import new_uuid  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    event = Event(
        id=new_uuid(),
        venue_id=body["venue_id"],
        name=body["name"],
        event_type=body.get("event_type", "other"),
        scheduled_start=datetime.fromisoformat(body["scheduled_start"]),
        scheduled_end=datetime.fromisoformat(body["scheduled_end"]),
        estimated_attendance=body.get("estimated_attendance"),
        status=body.get("status", "SCHEDULED"),
        data_source=body.get("data_source", "SIMULATED"),
        metadata_=body.get("metadata", {}),
    )
    db.add(event)
    await db.flush()
    return _event_to_dict(event)


@router.get("/{event_id}")
async def get_event(event_id: str, db: DBSession) -> dict:
    """Get a single event with venue details."""
    stmt = (
        select(Event, Venue)
        .join(Venue, Event.venue_id == Venue.id)
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    event, venue = row
    d = _event_to_dict(event)
    d["venue"] = _venue_to_dict(venue)
    return d


@router.get("/{event_id}/venue")
async def get_event_venue(event_id: str, db: DBSession) -> dict:
    """Get venue details for an event including GeoJSON point."""
    stmt = (
        select(Event, Venue)
        .join(Venue, Event.venue_id == Venue.id)
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    _, venue = row
    return _venue_to_dict(venue)


@router.post("/{event_id}/simulate", status_code=200)
async def trigger_simulation(event_id: str, db: DBSession) -> dict:
    """
    Run T+20 and T+40 crowd simulations for the event.
    Persists crowd_forecasts, h3_demand_cells, and transport_supply_snapshots.
    Returns forecast IDs.
    """
    from datetime import datetime, timezone  # noqa: PLC0415
    from app.models.db.base import new_uuid  # noqa: PLC0415
    from app.models.db.crowd_forecast import CrowdForecast  # noqa: PLC0415
    from app.models.db.h3_demand_cell import H3DemandCell  # noqa: PLC0415
    from app.models.db.transport_supply_snapshot import TransportSupplySnapshot  # noqa: PLC0415
    from app.simulator.crowd import simulate_crowd_exit  # noqa: PLC0415
    from app.simulator.transport import get_supply_snapshot  # noqa: PLC0415

    # Load event + venue
    stmt = (
        select(Event, Venue)
        .join(Venue, Event.venue_id == Venue.id)
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    event, venue = row

    attendance = event.estimated_attendance or 34_000
    gates = venue.gates or []
    lat = float(text("ST_Y(location::geometry)")) if False else 12.9789  # fallback; real PostGIS in Docker
    lon = 77.5996

    # Try to get real coordinates from PostGIS if available
    try:
        coord_result = await db.execute(
            text("SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon FROM venues WHERE id = :id"),
            {"id": str(venue.id)},
        )
        coord_row = coord_result.first()
        if coord_row:
            lat, lon = float(coord_row.lat), float(coord_row.lon)
    except Exception:
        pass  # use fallback coordinates

    now = datetime.now(tz=timezone.utc)
    forecasts_created = []
    snapshots_created = 0

    for horizon in [20, 40]:
        sim = simulate_crowd_exit(
            event_id=event_id,
            t_plus_minutes=horizon,
            attendance=attendance,
            venue_lat=lat,
            venue_lon=lon,
            gates=gates,
        )

        forecast_id = new_uuid()
        forecast = CrowdForecast(
            id=forecast_id,
            event_id=event_id,
            forecast_time=now,
            horizon_minutes=horizon,
            total_demand=sim.total_demand,
            peak_zone_h3=sim.peak_zone_h3,
            confidence=sim.confidence,
            data_source="SIMULATED",
        )
        db.add(forecast)
        await db.flush()

        # Persist H3 cells
        for cell in sim.h3_cells:
            db.add(H3DemandCell(
                forecast_id=forecast_id,
                event_id=event_id,
                h3_id=cell.h3_id,
                resolution=cell.resolution,
                center_lat=cell.center_lat,
                center_lon=cell.center_lon,
                demand_persons=cell.demand_persons,
                demand_category=cell.demand_category,
                horizon_minutes=horizon,
                data_source="SIMULATED",
            ))

        # Transport supply snapshot per mode
        supply = get_supply_snapshot(
            event_id=event_id,
            time_horizon=horizon,
            total_demand=sim.total_demand,
            venue_lat=lat,
            venue_lon=lon,
            attendance=attendance,
        )
        for mode_result in supply.modes:
            db.add(TransportSupplySnapshot(
                id=new_uuid(),
                event_id=event_id,
                snapshot_time=now,
                time_horizon=horizon,
                mode=mode_result.mode,
                capacity=mode_result.capacity_per_hour,
                vehicles=mode_result.vehicles_available,
                frequency_mins=mode_result.frequency_minutes,
                operational=mode_result.operational,
                gap_persons=mode_result.gap_persons,
                data_source="SIMULATED",
                notes=mode_result.notes,
            ))
            snapshots_created += 1

        forecasts_created.append({
            "forecast_id": forecast_id,
            "horizon_minutes": horizon,
            "total_demand": sim.total_demand,
            "h3_cell_count": len(sim.h3_cells),
        })

    await db.flush()
    return {
        "event_id": event_id,
        "forecasts": forecasts_created,
        "transport_snapshots": snapshots_created,
        "data_source": "SIMULATED",
        "simulated_at": now.isoformat(),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _event_to_dict(e: Event) -> dict:
    return {
        "event_id":             e.id,
        "venue_id":             e.venue_id,
        "name":                 e.name,
        "event_type":           e.event_type,
        "scheduled_start":      e.scheduled_start.isoformat() if e.scheduled_start else None,
        "scheduled_end":        e.scheduled_end.isoformat() if e.scheduled_end else None,
        "estimated_end":        e.estimated_end.isoformat() if e.estimated_end else None,
        "estimated_attendance": e.estimated_attendance,
        "actual_attendance":    e.actual_attendance,
        "status":               e.status,
        "data_source":          e.data_source,
        "metadata":             e.metadata_ or {},
        "created_at":           e.created_at.isoformat() if e.created_at else None,
    }


def _venue_to_dict(v: Venue) -> dict:
    return {
        "venue_id":       v.id,
        "name":           v.name,
        "city":           v.city,
        "address":        v.address,
        "total_capacity": v.total_capacity,
        "h3_center_res7": v.h3_center_res7,
        "gates":          v.gates or [],
        "metro_stations": v.metro_stations or [],
        "bus_stops":      v.bus_stops or [],
    }
