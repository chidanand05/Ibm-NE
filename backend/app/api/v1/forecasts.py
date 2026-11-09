"""Crowd forecast endpoints — Sub-task 2.1b."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import DBSession
from app.models.db.crowd_forecast import CrowdForecast
from app.models.db.h3_demand_cell import H3DemandCell

from sqlalchemy import select

router = APIRouter()


@router.get("/")
async def list_forecasts(
    db: DBSession,
    event_id: str | None = Query(None, description="Filter by event ID"),
    horizon: int | None = Query(None, description="Filter by horizon_minutes (20 or 40)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List crowd forecasts, optionally filtered by event and horizon."""
    stmt = select(CrowdForecast).order_by(CrowdForecast.created_at.desc()).limit(limit).offset(offset)
    if event_id:
        stmt = stmt.where(CrowdForecast.event_id == event_id)
    if horizon is not None:
        stmt = stmt.where(CrowdForecast.horizon_minutes == horizon)
    result = await db.execute(stmt)
    forecasts = result.scalars().all()
    return {
        "items": [_forecast_to_dict(f) for f in forecasts],
        "total": len(forecasts),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{forecast_id}")
async def get_forecast(forecast_id: str, db: DBSession) -> dict:
    """Get a single forecast with its H3 demand cells."""
    stmt = select(CrowdForecast).where(CrowdForecast.id == forecast_id)
    result = await db.execute(stmt)
    forecast = result.scalar_one_or_none()
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"Forecast {forecast_id} not found")

    # Load H3 cells for this forecast
    cell_stmt = (
        select(H3DemandCell)
        .where(H3DemandCell.forecast_id == forecast_id)
        .order_by(H3DemandCell.demand_persons.desc())
    )
    cell_result = await db.execute(cell_stmt)
    cells = cell_result.scalars().all()

    d = _forecast_to_dict(forecast)
    d["h3_cells"] = [_cell_to_dict(c) for c in cells]
    return d


# ── Helpers ────────────────────────────────────────────────────────────────────

def _forecast_to_dict(f: CrowdForecast) -> dict:
    return {
        "forecast_id":     f.id,
        "event_id":        f.event_id,
        "forecast_time":   f.forecast_time.isoformat() if f.forecast_time else None,
        "horizon_minutes": f.horizon_minutes,
        "total_demand":    f.total_demand,
        "peak_zone_h3":    f.peak_zone_h3,
        "confidence":      float(f.confidence) if f.confidence is not None else None,
        "data_source":     f.data_source,
        "created_at":      f.created_at.isoformat() if f.created_at else None,
    }


def _cell_to_dict(c: H3DemandCell) -> dict:
    return {
        "id":              c.id,
        "forecast_id":     c.forecast_id,
        "event_id":        c.event_id,
        "h3_id":           c.h3_id,
        "resolution":      c.resolution,
        "center_lat":      float(c.center_lat) if c.center_lat is not None else None,
        "center_lon":      float(c.center_lon) if c.center_lon is not None else None,
        "demand_persons":  c.demand_persons,
        "demand_category": c.demand_category,
        "horizon_minutes": c.horizon_minutes,
        "data_source":     c.data_source,
    }
